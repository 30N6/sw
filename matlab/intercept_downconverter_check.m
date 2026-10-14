filename            = "analysis-20261012-171956.log";
dwell_frequency     = 450;
fs_u                = 240e3;
fs_d                = 40e3;

reload = 1;

if reload
    lines = readlines(filename);
    
    input_data = struct("stream_index", [], "channel_index", [], "frequency", [], "u_iq", [], "d_iq", []);
    num_elements = 0;
    
    for ii = 1:length(lines)-1
        line_data = jsondecode(lines(ii));
        if ~isfield(line_data.data, "stream_index")
            continue;
        end

        if line_data.data.type ~= "downconversion"
            continue
        end
        num_elements = num_elements + 1;
        
        input_data(num_elements).stream_index   = line_data.data.stream_index;
        input_data(num_elements).channel_index  = line_data.data.channel_index;
        input_data(num_elements).lo_index       = line_data.data.lo_index;
        input_data(num_elements).lo_frequency   = line_data.data.lo_freq;
        input_data(num_elements).frequency      = dwell_frequency + (line_data.data.channel_index - 256) * (61.44/512);
        input_data(num_elements).u_iq           = line_data.data.data_uI + 1j * line_data.data.data_uQ;
        input_data(num_elements).d_iq           = line_data.data.data_dI + 1j * line_data.data.data_dQ;
        
        input_data(num_elements).fft_data_u       = fftshift(fft(input_data(num_elements).u_iq));
        input_data(num_elements).fft_power_u      = abs(input_data(num_elements).fft_data_u).^2;
        input_data(num_elements).fft_power_u_dB   = 10*log10(input_data(num_elements).fft_power_u);

        input_data(num_elements).fft_data_d       = fftshift(fft(input_data(num_elements).d_iq));
        input_data(num_elements).fft_power_d      = abs(input_data(num_elements).fft_data_d).^2;
        input_data(num_elements).fft_power_d_dB   = 10*log10(input_data(num_elements).fft_power_d);        
    end
end

%%

%filtered_data = input_data([input_data.frequency] == analysis_frequency);

unique_freqs = sort(unique([input_data.frequency]));

for ii = 1:length(unique_freqs)
    freq = unique_freqs(ii);
    filtered_data = input_data([input_data.frequency] == freq);

    fft_len_u = length(filtered_data(1).fft_data_u);
    x_u = ([0:(fft_len_u-1)] - fft_len_u/2) * (fs_u/fft_len_u) + filtered_data(1).frequency * 1e6;

    fft_len_d = length(filtered_data(1).fft_data_d);
    x_d = ([0:(fft_len_d-1)] - fft_len_d/2) * (fs_d/fft_len_d);

    unique_los = unique([filtered_data.lo_frequency]);
    
    for jj = 1:length(unique_los)
        filtered_data_2 = filtered_data([filtered_data.lo_frequency] == unique_los(jj));

        figure(ii*4 + jj);
        
        lo_freq = -unique_los(jj) + filtered_data(1).frequency * 1e6;

        subplot(1,2,1);
        plot(x_u, [filtered_data_2(1).fft_power_u_dB], [lo_freq, lo_freq], [-100, 20]);
    
        subplot(1,2,2);
        plot(x_d, [filtered_data_2(1).fft_power_d_dB]);
        
        title(sprintf("freq=%f lo=%d --> %f", freq, jj, unique_los(jj)));
    end
end    