filename            = "analysis-20261012-171956.log";
fs_u                = 240e3;

reload = 1;

if reload
    lines = readlines(filename);
    
    input_data = struct("stream_index", [], "fft_accum", [], "est_valid", [], "est_center", []);
    num_elements = 0;
    
    for ii = 1:length(lines)-1
        line_data = jsondecode(lines(ii));
        if ~isfield(line_data.data, "stream_index")
            continue;
        end

        if line_data.data.type ~= "freq_est"
            continue
        end
        num_elements = num_elements + 1;
        
        input_data(num_elements).stream_index   = line_data.data.stream_index;
        input_data(num_elements).est_valid      = line_data.data.est_valid;
        input_data(num_elements).est_center     = line_data.data.est_center;
       
        input_data(num_elements).fft_accum      = line_data.data.fft_accum_power;
        input_data(num_elements).fft_accum_dB   = 10*log10(input_data(num_elements).fft_accum);
    end
end

%%

filtered_data = input_data(any([input_data.est_valid]));

for ii = 1:length(filtered_data)
    fft_len = length(filtered_data(ii).fft_accum);
    x = ([0:(fft_len-1)] - fft_len/2) * (fs_u/fft_len);

    figure(100 + ii);
    plot(x, [filtered_data(ii).fft_accum_dB]);
    hold on;
    for jj = 1:4
        if filtered_data(ii).est_valid(jj)
            est_x = -(0.5 - [filtered_data(ii).est_center(jj), filtered_data(ii).est_center(jj)]) * fs_u;
            est_y = [-80, -20];
            plot(est_x, est_y);
        end
    end
    hold off;

    %, [lo_freq, lo_freq], [-100, 20]

    title(sprintf("stream_index=%d", filtered_data(ii).stream_index));
end    