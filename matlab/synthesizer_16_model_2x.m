L           = 16;
coef_width  = 20;
data_width  = 12;

fs_in           = 61.44e6;
fs_out          = fs_in / (0.5*L);
data_length_out = round(fs_out * 500e-6);
data_length_in  = 0.5 * L * data_length_out;

H_a = get_analysis_sub_filters(L, coef_width);
H_s = get_synthesis_sub_filters(L, coef_width);

filename = sprintf("./channelizer_test_data_2025_01_08_%d.txt", L);

for frame = 1:1
    d = gen_stim_data(data_length_in, data_width, frame, fs_in);
    x_pp = analysis_demux(L, d);
    
    x_filtered = zeros(size(x_pp));
    for channel = 1:L
        x = conv(H_a(channel, :), x_pp(channel, :)) ./ (2^(coef_width - 1));
        x_filtered(channel, :) = x(1:size(x_pp, 2));
    end

    %figure(1); plot(real(x_filtered.'));

    x_analysis_output = zeros(size(x_filtered));
    for slice = 1:size(x_filtered, 2)
        %x_analysis_output(:, sample) = x_filtered(:, sample);
        x_analysis_output(:, slice) = L * ifft(x_filtered(:, slice));
    end
    
    x_analysis_output_u = x_analysis_output;

    x_mod = ones(1, size(x_analysis_output, 2));
    x_mod(2:2:end) = -1;

    for channel = 1:L
        if mod(channel - 1, 2) == 1
            x_analysis_output(channel, :) = x_analysis_output(channel, :) .* x_mod;
        end        
    end
    
    x_synthesis_fft = zeros(size(x_analysis_output));
    for slice = 1:size(x_synthesis_fft, 2)
        x_synthesis_fft(:, slice) = fft(x_analysis_output_u(:, slice));
    end

    x_synthesis_filtered = zeros(size(x_pp));
    for channel = 1:L
        x = conv(H_s(channel, :), x_synthesis_fft(channel, :)) ./ (2^(coef_width - 1));
        x_synthesis_filtered(channel, :) = x(1:size(x_pp, 2));
    end
    
    x_synthesis_output = synthesis_mux(L, x_synthesis_filtered);

    %remap_i = [33:64, 1:32];
    remap_i = [(L/2)+1:L, 1:L/2]
    x_analysis_output_remapped = x_analysis_output(remap_i, :);

    %figure(2); plot(10*log10(abs(x_analysis_output.')));

    plot_analysis_data(L, x_analysis_output_remapped);
    %plot_analysis_data(L, x_analysis_output);

    figure(9); 
    subplot(2,1,1);
    instfreq(d, fs_in);
    subplot(2,1,2);
    instfreq(x_synthesis_output, fs_in);
    
    figure(11);
    ax1 = subplot(2,1,1);
    plot(1:length(d), real(d), 1:length(d), imag(d));
    ax2 = subplot(2,1,2);
    plot(1:length(x_synthesis_output), real(x_synthesis_output), 1:length(x_synthesis_output), imag(x_synthesis_output));
    linkaxes([ax1, ax2], 'x');
    
    figure(12);
    plot(1:length(x_synthesis_output), 20*log10(abs(x_synthesis_output)));

    save_test_data(filename, d);
    
    break;
end

function save_test_data(filename, d)
    fh = fopen(filename, "w");

    for ii = 1:length(d)
        fprintf(fh, "%d %d\n", real(d(ii)), imag(d(ii)));
    end
    fclose(fh);
end

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
    M = 8;          % taps per subband
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
    M = 6;          % taps per subband
    N = M*L;        % total taps
    alpha = 0.950;    %broadening factor
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
