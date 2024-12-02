function [r, fs_out] = channelizer_64_model(data_in, fs)
    L               = 64;
    coef_width      = 18;
    fs_in           = 61.44e6;
    fs_out          = fs_in / (0.5*L);

    assert (fs == fs_in);
    
    H = get_sub_filters(L, coef_width);
    
    d = data_in;
    x_pp = get_polyphase_filter_inputs(L, data_in);
    
    x_filtered = zeros(size(x_pp));
    for channel = 1:L
        x = conv(H(channel, :), x_pp(channel, :)) ./ (2^(coef_width - 1));
        x_filtered(channel, :) = x(1:size(x_pp, 2));
    end

    %figure(1); plot(real(x_filtered.'));

    x_output = zeros(size(x_filtered));
    for sample = 1:size(x_filtered, 2)
        %x_output(:, sample) = x_filtered(:, sample);
        x_output(:, sample) = L * ifft(x_filtered(:, sample));
    end

    x_mod = ones(1, size(x_output, 2));
    x_mod(2:2:end) = -1;
    for channel = 1:L
        if mod(channel - 1, 2) == 1
            x_output(channel, :) = x_output(channel, :) .* x_mod;
        end        
    end
    
    remap_i = [(L/2)+1:L, 1:L/2];
    x_output_remapped = x_output(remap_i, :).';

    %for ii = 1:L
    %    if ~bitget(chan_mask, ii)
    %        x_output_remapped(:, ii) = 0;
    %    end
    %end
    
    %plot_output_data(L, x_output_remapped);

    r = x_output_remapped;
end

function plot_output_data(L, d)
    num_plots = 2; %1; %8;
    for f = 1:num_plots
        figure(f);        
        L_offset = (f-1)*(L/num_plots);
        for ii = (1+L_offset):(L_offset + L/num_plots)
            subplot(L/num_plots, 1, ii - L_offset);
            plot(1:size(d, 2), real(d(ii, :)), 1:size(d, 2), imag(d(ii, :)));
        end
    end
end

function r = get_polyphase_filter_inputs(L, d)
    output_len = (length(d) / L) * 2;
    r = zeros(L, output_len - 1);
    output_i = zeros(L, output_len - 1);
    
    for channel = 0:(L-1)
        input_offset = 1 + ((L - 1) - channel);
        idx = input_offset:(L/2):length(d);
        output_i(channel + 1, :) = idx(1:output_len-1);
    end
    
    r = d(output_i);
end

function H_f = get_sub_filters(L, output_width)
    %L = 64;         % subbands
    M = 12;         % taps per subband
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
