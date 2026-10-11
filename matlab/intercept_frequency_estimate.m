filename            = "analysis-20261010-154852.log";
dwell_frequency     = 450;
analysis_frequency  = 462.360;
fs = (61.44 / 512) * 2;

fft_edge_width = 40;
threshold_factor = 10.0;
max_signal_half_width = 15; %channels

lines = readlines(filename);

input_data = struct("stream_index", [], "channel_index", [], "frequency", [], "iq", []);
num_elements = 0;

for ii = 1:length(lines)-1
    line_data = jsondecode(lines(ii));
    if ~isfield(line_data.data, "stream_index")
        continue;
    end
    
    num_elements = num_elements + 1;

    input_data(num_elements).stream_index   = line_data.data.stream_index;
    input_data(num_elements).channel_index  = line_data.data.channel_index;
    input_data(num_elements).frequency      = dwell_frequency + (line_data.data.channel_index - 256) * (61.44/512);
    input_data(num_elements).iq             = line_data.data.I + 1j * line_data.data.Q;

    input_data(num_elements).total_power_dB = 10*log10(sum(abs(input_data(num_elements).iq)));

    windowed_data = input_data(num_elements).iq .* hann(length(input_data(num_elements).iq));

    input_data(num_elements).fft_data       = fftshift(fft(windowed_data));
    
    input_data(num_elements).fft_data(1:fft_edge_width) = 0;
    input_data(num_elements).fft_data((end - fft_edge_width):end) = 0;
    
    input_data(num_elements).fft_power      = abs(input_data(num_elements).fft_data).^2;
    input_data(num_elements).fft_power_dB   = 10*log10(input_data(num_elements).fft_power);

    input_data(num_elements).power_threshold = median(input_data(num_elements).fft_power) * threshold_factor;
    input_data(num_elements).power_threshold_dB = 10*log10(input_data(num_elements).power_threshold);
end

%%

%filtered_data = input_data([input_data.frequency] == analysis_frequency);

unique_freqs = unique([input_data.frequency])

for ii = 1:length(unique_freqs)
    freq = unique_freqs(ii);
    filtered_data = input_data([input_data.frequency] == freq);

    %filtered_data = input_data([input_data.frequency] == analysis_frequency);
    
    fft_len = length(filtered_data(1).fft_data);
    x = ([0:(fft_len-1)] - fft_len/2) * (fs/fft_len) + filtered_data(1).frequency;

    %figure(ii);
    %plot(x, [filtered_data.fft_power_dB]);
    
    fft_power_dB = [filtered_data.fft_power_dB];
    threshold_dB = 10*log10([filtered_data.power_threshold]);
    peaks = fft_power_dB;
    for jj = 1:length(threshold_dB)
        peaks(fft_power_dB(:, jj) < threshold_dB(jj), jj) = -Inf;
    end
    
    %plot(x, peaks, 'o');

    normalized_power_dB = fft_power_dB;
    for jj = 1:length(threshold_dB)
        normalized_power_dB(:, jj) = normalized_power_dB(:, jj) - threshold_dB(jj);
    end
    peaks = normalized_power_dB;
    for jj = 1:length(threshold_dB)
        peaks(normalized_power_dB(:, jj) < 0, jj) = -Inf;
    end

    %[vals, idx] = maxk(signal, N); 

    figure(ii);
    plot(x, normalized_power_dB, 'o');
    grid('on');

    max_index = zeros(1, length(filtered_data));
    max_power = zeros(1, length(filtered_data));
    colors = ["r", "g", "b"];
    for i_peak = 1:3
        for jj = 1:length(threshold_dB)
            [max_power(jj), max_index(jj)] = max(normalized_power_dB(:, jj));
            
            upper_done = 0;
            lower_done = 0;
            for kk = 1:max_signal_half_width
                upper = max_index(jj) + kk;
                lower = max_index(jj) - kk;
                if (upper < fft_len) && (normalized_power_dB(upper, jj) > 0) && ~upper_done
                    normalized_power_dB(upper, jj) = -Inf;
                else
                    upper_done = 1;
                end
                if (lower > 0) && (normalized_power_dB(lower, jj) > 0) && ~lower_done
                    normalized_power_dB(lower, jj) = -Inf;
                else
                    lower_done = 1;
                end
            end

            normalized_power_dB(max_index(jj), jj) = -Inf;
        end

        hold on;
        plot(x(max_index), max_power, colors(i_peak) + "x", "MarkerSize", 5);
        hold off;
    end

end    