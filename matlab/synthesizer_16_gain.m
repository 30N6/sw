L           = 16;
coef_width  = 20;
data_width  = 12;

fs_in           = 61.44e6;
fs_out          = fs_in / (0.5*L);
data_length_out = round(fs_out * 5000e-6);
data_length_in  = 0.5 * L * data_length_out;

H_a = get_analysis_sub_filters(L, coef_width);
H_s = get_synthesis_sub_filters(L, coef_width);

full_active_channels = 3:15;

results_num_channels = [];
results_iq_gain = [];
results_amp_gain = [];

use_mean = 0;

for jj=1:100
    x_analysis_output_u = zeros([L, data_length_out]);
    
    num_channels_active = randi(length(full_active_channels));

    chan_i = randsample(full_active_channels, num_channels_active);
    for ii = chan_i
        %x_analysis_output_u(ii, :) = exp(1j * pi * randn(1)); %exp(1j * pi * rand([1, data_length_out]));
        x_analysis_output_u(ii, :) = exp(1j * pi * randn([1, data_length_out]) * 1);
    end
    
    x_synthesis_fft = zeros(size(x_analysis_output_u));
    for slice = 1:size(x_synthesis_fft, 2)
        x_synthesis_fft(:, slice) = fft(x_analysis_output_u(:, slice));
    end
    
    x_synthesis_filtered = zeros(size(x_analysis_output_u));
    for channel = 1:L
        x = conv(H_s(channel, :), x_synthesis_fft(channel, :)) ./ (2^(coef_width - 1));
        x_synthesis_filtered(channel, :) = x(1:size(x_analysis_output_u, 2));
    end
    
    x_synthesis_output = synthesis_mux(L, x_synthesis_filtered);
    
    %figure(9); 
    %%instfreq(x_synthesis_output, fs_in);
    %spectrogram(x_synthesis_output);
    %
    %figure(11);
    %plot(1:length(x_synthesis_output), real(x_synthesis_output), 1:length(x_synthesis_output), imag(x_synthesis_output));
    %
    %figure(12);
    %plot(1:length(x_synthesis_output), 20*log10(abs(x_synthesis_output)));
    
    if use_mean 
        input_max_iq        = mean([abs(real(x_analysis_output_u(:))), abs(imag(x_analysis_output_u(:)))], "all");
        input_max_amplitude = mean(abs(x_analysis_output_u(:)));
        
        output_max_iq        = mean([abs(real(x_synthesis_output)), abs(imag(x_synthesis_output))], "all");
        output_max_amplitude = mean(abs(x_synthesis_output));
    
        results_num_channels = [results_num_channels, num_channels_active];
        results_iq_gain      = [results_iq_gain, output_max_iq/input_max_iq];
        results_amp_gain     = [results_amp_gain, output_max_amplitude/input_max_amplitude];
    else
        input_max_iq         = max([abs(real(x_analysis_output_u(:))), abs(imag(x_analysis_output_u(:)))], [], "all");
        input_max_amplitude  = max(abs(x_analysis_output_u(:)));
        
        output_max_iq        = max([abs(real(x_synthesis_output)), abs(imag(x_synthesis_output))], [],"all");
        output_max_amplitude = max(abs(x_synthesis_output));
    
        results_num_channels = [results_num_channels, num_channels_active];
        results_iq_gain      = [results_iq_gain, output_max_iq/input_max_iq];
        results_amp_gain     = [results_amp_gain, output_max_amplitude/input_max_amplitude];
    end

    disp(jj);
end

%%
figure(100);

x_f = 1:13;
y_f = 5.5*sqrt(x_f) - 2.75;

plot(results_num_channels, results_iq_gain, 'o', results_num_channels, results_amp_gain, 'o', x_f, y_f);
grid on;

figure(101);
plot(results_num_channels, 1./results_iq_gain, 'o', results_num_channels, 1./results_amp_gain, 'o', x_f, 1./y_f, x_f,  2.^-ceil(log2(y_f)), 'o');
grid on;



function plot_analysis_data(L, d)
    num_plots = 1; %8;
    for f = 1:num_plots
        figure(f);        
        L_offset = (f-1)*(L/num_plots);
        for ii = (1+L_offset):(L_offset + L/num_plots)
            subplot(L/num_plots, 1, ii - L_offset);
            plot(1:size(d, 2), real(d(ii, :)), 1:size(d, 2), imag(d(ii, :)));
        end
    end
end

function r = analysis_demux(L, d)
    output_len = (length(d) / L) * 2;
    r = zeros(L, output_len);
    output_i = zeros(L, output_len);
    d_padded = [d, zeros([1, L/2])];
    
    for channel = 0:(L-1)
        input_offset = 1 + ((L - 1) - channel);
        idx = input_offset:(L/2):(length(d) + L/2);
        output_i(channel + 1, :) = idx(1:output_len);
    end
    
    r = d_padded(output_i);
end

function r = synthesis_mux(L, d)
    output_len = length(d) * L / 2;
    r = zeros([1, output_len]);

    padded_d = [zeros(L, 1), d];
    summed_d = padded_d(1:L/2, 1:length(d)) + d(L/2+1:end, :);

    i_row = mod([output_len-1:-1:0], L/2) + 1;
    %i_row = mod([0:output_len-1], L) + 1;
    i_col = floor((0:(output_len-1)) / (L/2)) + 1;
    
    ii = sub2ind(size(summed_d), i_row, i_col);

    r = summed_d(ii);
end

function H_f = get_analysis_sub_filters(L, output_width)
    %L = 64;         % subbands
    M = 12;          % taps per subband
    N = M*L;        % total taps
    alpha = 0.8;    %broadening factor
    beta = 0.8;     %shape factor
    H = kaiser(N,beta*M)' .* sinc(((-N/2:N/2-1))/(alpha*L));
    
    H_s = zeros(L, 2*N/L);
    for ii = 1:L
        idx = ii:L:N;
        H_z1 = H(idx);
        H_z2 = zeros(1, 2*length(H_z1));
        H_z2(1:2:end) = H_z1;
        H_s(ii, :) = H_z2;
    end

    H_f = round(H_s * (2^(output_width - 1)));
    H_f(H_f > (2^(output_width - 1) - 1)) = 2^(output_width - 1) - 1;
    %H_f = round(H * (2^(output_width - 1)));
    %H_f(H_f > (2^(output_width - 1) - 1)) = 2^(output_width - 1) - 1;
end

function H_f = get_synthesis_sub_filters(L, output_width)
    %L = 64;         % subbands
    M = 8;          % taps per subband
    N = M*L;        % total taps
    alpha = 0.980;    %broadening factor
    beta = 0.8;     %shape factor
    H = kaiser(N,beta*M)' .* sinc(((-N/2:N/2-1))/(alpha*L));
    
    H_s = zeros(L, 2*N/L);
    for ii = 1:L
        coef_idx = (1:L:N) - ii + 1;
        
        H_z1 = zeros([1, length(coef_idx)]);  %H(idx);
        for jj = 1:length(H_z1)
            if coef_idx(jj) <= 0
                H_z1(jj) = 0;
            else
                H_z1(jj) = H(coef_idx(jj));
            end
        end        
        
        H_z2 = zeros(1, 2*length(H_z1));
        H_z2(1:2:end) = H_z1;
        H_s(ii, :) = H_z2;
    end

    H_f = round(H_s * (2^(output_width - 1)));
    H_f(H_f > (2^(output_width - 1) - 1)) = 2^(output_width - 1) - 1;
    %H_f = round(H * (2^(output_width - 1)));
    %H_f(H_f > (2^(output_width - 1) - 1)) = 2^(output_width - 1) - 1;
end

function d = gen_stim_data(N, width, frame, fs)
    f = linspace(-fs/2, 0, N);
    %f = 0.005*fs;

    %f = fs*0.27;
    t = [0:(N-1)] .* (1/fs);
    x = exp(2j*pi.*f.*t);   
    
    %re = round(2^(width-1) * real(x)) + randi([-128, 127], 1, N);
    %im = round(2^(width-1) * imag(x)) + randi([-128, 127], 1, N);
    re = round((2^(width-1)-1) * real(x));
    im = round((2^(width-1)-1) * imag(x));
    
    d = re + 1j*im;
end
