%filename = "analysis-20250315-220724.log";
%filename = "analysis-20250315-224035.log";
%filename = "analysis-20250315-225555.log";
filename = "analysis-20250315-233607.log";


Fs = 7.68e6;
dt = 1/Fs;
L = 2048;

reload = 1;

if reload
    lines = readlines(filename);
    scan_reports = [];
    init_done = false;
    
    for ii = 1:length(lines)
        if strlength(lines(ii)) <= 1
            continue
        end
    
        decoded_line = jsondecode(lines(ii));
        data = decoded_line.data;
        if ~isfield(data, 'iq_data')
            continue;
        end    

        if ~init_done
            scan_reports = data;
            init_done = true;
        else
            scan_reports(end + 1) = data;
        end
    end

    for ii = 1:length(scan_reports)
        scan_reports(ii).iq_data = scan_reports(ii).iq_data(:, 1) + 1j * scan_reports(ii).iq_data(:, 2);
        %scan_reports(ii).iq_data = scan_reports(ii).iq_data - mean(scan_reports(ii).iq_data) * 1.0; %0.999;
        %if (mod(scan_reports(ii).channel_index, 2) == 1)
        %    scan_reports(ii).iq_data = baseband(scan_reports(ii).iq_data);
        %end
        scan_reports(ii).iq_length = length(scan_reports(ii).iq_data);
        scan_reports(ii).mean_power_dB = 20*log10(mean(abs(scan_reports(ii).iq_data)));
        scan_reports(ii).iq_data_padded = paddata(scan_reports(ii).iq_data, L);        

        scan_reports(ii).iq_phase = unwrap(atan2(imag(scan_reports(ii).iq_data), real(scan_reports(ii).iq_data)));
        scan_reports(ii).iq_freq = (1/(2*pi)) * diff(scan_reports(ii).iq_phase) / dt;        
        
        scan_reports(ii).timestamp_sec = scan_reports(ii).hw_timestamp * (1/(4*61.44e6));
        
        %[scan_reports(ii).fft_freq_mean, scan_reports(ii).fft_freq_std] = scan_reports(ii).iq_data_padded, Fs);
        scan_reports(ii).lfm_r_squared = scan_reports(ii).analysis.lfm_r_squared;
        scan_reports(ii).lfm_slope = scan_reports(ii).analysis.lfm_slope;
    end

    scan_reports = scan_reports';
end


freqs = unique([scan_reports.channel_freq]);
figure(10);
for ii = 1:length(freqs)
   subplot(length(freqs), 1, ii)
   r = scan_reports([scan_reports.channel_freq] == freqs(ii));
   plot([r.hw_timestamp] * (1/(4*61.44e6)), [r.mean_power_dB], 'o');
end
% 
% freqs = unique([scan_reports.dwell_freq]);
% figure(11);
% for ii = 1:length(freqs)
%   subplot(length(freqs), 1, ii)
%   r = scan_reports([scan_reports.dwell_freq] == freqs(ii));
%   plot([r.hw_timestamp] * (1/(4*61.44e6)), [r.r_squared_fsk_min], 'o', [r.hw_timestamp] * (1/(4*61.44e6)), [r.r_squared_fsk_max], 'o');
% end

figure(1);
for ii = 1:length(freqs)
   subplot(length(freqs), 1, ii)
   r = scan_reports([scan_reports.channel_freq] == freqs(ii));
   plot([r.hw_timestamp] * (1/(4*61.44e6)), [r.lfm_r_squared], 'o');
end


%channel_filter_freq = 1340.80;
channel_filter_freq = 1336.96;
%channel_filter_freq = 1338.80;

state_match = false(length(scan_reports), 1);
for ii = 1:length(scan_reports)
    state_match(ii) = scan_reports(ii).controller_state == "TX_LISTEN";
end
%freq_match      = ([scan_reports.dwell_freq] == dwell_filter_freq).';
freq_match      = ([scan_reports.channel_freq] == channel_filter_freq).';
%freq_match      = ([scan_reports.channel_freq] > 0).';
length_match    = ([scan_reports.iq_length] > 128).';
power_match     = ([scan_reports.mean_power_dB] > 20).';
timestamp_match = ([scan_reports.timestamp_sec] > 0).' & ([scan_reports.timestamp_sec] < 9999).';
%mod_match        = ([scan_reports.cvbs_xcorr_ratio_1] > 0.2).' & ([scan_reports.cvbs_xcorr_ratio_3] < 0.2).';
filtered_reports = scan_reports(freq_match & length_match & state_match & power_match & timestamp_match); %& mod_match);

figure(20);
subplot(3,1,1);
%plot([filtered_reports.mean_power_dB]);
%plot([filtered_reports.timestamp] * (1/(4*61.44e6)), [filtered_reports.mean_power_dB], 'o');
plot([filtered_reports.mean_power_dB], 'o');
subplot(3,1,2);
plot([filtered_reports.iq_length], [filtered_reports.mean_power_dB], 'o');

%%
offset = 0;
num_rows = 4;
num_cols = 4;

figure(2);
ax1 = zeros(num_rows, num_cols);
figure(3);
ax2 = zeros(num_rows, num_cols);

for row = 1:num_rows
    for col = 1:num_cols
        plot_index = (row-1) * num_cols + col;
        d = filtered_reports(plot_index + offset);        

        channel_freq = d.dwell_freq + (Fs/2)/1e6 * (d.channel_index - 8);
        %s = sprintf("[%d] %d %d: %.1f %0.3f %0.3f", plot_index + offset, d.dwell_freq, d.channel_index, channel_freq, d.r_squared_fsk_max, d.r_squared_fsk_min);
        s = sprintf("[%d]: %.1f %0.3f", plot_index + offset, channel_freq, d.lfm_r_squared);
        
        t = (0:d.iq_length-1).' / Fs;
        y = d.iq_data(1:d.iq_length);
        
        figure(2);
        ax1(row, col) = subplot(num_rows,num_cols,plot_index);
        plot(t, real(y), t, imag(y));
        title(s);
    end
end

for row = 1:num_rows
    for col = 1:num_cols
        plot_index = (row-1) * num_cols + col;
        d = filtered_reports(plot_index + offset);        

        channel_freq = d.dwell_freq + (Fs/2)/1e6 * (d.channel_index - 8);
        %s = sprintf("[%d] %d %d: %.1f %0.3f %0.3f", plot_index + offset, d.dwell_freq, d.channel_index, channel_freq, d.r_squared_fsk_max, d.r_squared_fsk_min);
        s = sprintf("[%d]: %.1f %0.3f", plot_index + offset, channel_freq, d.lfm_r_squared);
        
        t = (0:d.iq_length-1).' / Fs;
        y = d.iq_data(1:d.iq_length);
    
        figure(3);
        ax2(row, col) = subplot(num_rows,num_cols,plot_index);
        plot(t(1:end-1), d.iq_freq);
        title(s);
    end
end
%linkaxes(ax, 'y');


%%
d = filtered_reports(5);

rows = 6;

t = (0:d.iq_length-1).' / Fs;
y = d.iq_data(1:d.iq_length);

t_padded = (0:L-1).' / Fs;
y_padded = d.iq_data_padded;

figure(4);
ax_1 = subplot(rows,2,1);
plot(t, real(y), t, imag(y));

ax_2 = subplot(rows,2,2);
instfreq(y, Fs);
%linkaxes([ax_1, ax_2], 'x');

subplot(rows,2,3);
[c,lags] = xcorr(y);
plot(lags * (1/Fs) * 1e6, (abs(c)));

subplot(rows,2,4); 
X = fft(y_padded);
xc = abs(ifft(X .* conj(X)));

tx = t_padded(1:L/2);
xc = xc(1:L/2);

plot(tx, xc);

subplot(rows,2,5);
sf = compute_sfft(y_padded, 16);
imagesc(sf.');

subplot(rows,2,6);
Y = fft(y);
%plot(Fs/L*(-L/2:L/2-1), 20*log10(abs(fftshift(Y))),"LineWidth",1)
%plot(Fs/L*(-L/2:L/2-1), (abs(fftshift(Y))),"LineWidth",1)
plot(abs(fftshift(Y)));

subplot(rows,2,7);
plot(t, d.iq_phase);

subplot(rows,2,8);
plot(t(1:end-1), d.iq_freq);


subplot(rows,2,9);
%plot(t(1:end-2), freq_diff)
plot(xcorr(sf));

subplot(rows,2,10);
%plot(t(1:end-2), freq_diff_clipped);

subplot(rows,2,11);
%plot(t(1:end-2), cumsum(freq_diff_clipped));

subplot(rows, 2, 12);
plot(filter(ones(16,1), 1, d.iq_freq));

%fprintf("corr ratio: %f\n", s_xc/m_xc);

%%

d = filtered_reports(1);
%d = filtered_reports(10);

t_pad = (0:L-1).' / Fs;
y_pad = d.iq_data_padded;

t_freq = (0:length(d.iq_freq)-1).' * (1/Fs);
y_freq = d.iq_freq;

[fft_mean, fft_std] = get_fft_stats(d.iq_data_padded, Fs);

Y = fft(y_pad);
Y_shifted = abs(fftshift(Y));
f_shifted = (Fs/L)*(-L/2:L/2-1).';

figure(5);
subplot(4,2,1);
plot(t_pad, real(y_pad), t_pad, imag(y_pad));

subplot(4,2,2);
plot(t_freq, y_freq);

subplot(4, 2, 3);
y_max = max(Y_shifted);
plot(f_shifted, Y_shifted, [fft_mean, fft_mean], [0, y_max], ...
    [fft_mean - fft_std, fft_mean - fft_std], [0, y_max], ...
    [fft_mean + fft_std, fft_mean + fft_std], [0, y_max]);
%TODO: mean, std
%f_shifted, cumsum(Y_scaled)

circ_xcorr = abs(ifft(Y .* conj(Y)));
subplot(4, 2, 4);
plot(circ_xcorr(1:L/2));

%subplot(4, 2, 5);
%plot(1:length(det_length_hist), det_length_hist(1, :))

%%
function r = compute_sfft(data, N)
    r = zeros(length(data)/N, N);
    for ii = 1:(length(data)/N)
        r(ii, :) = fftshift(abs(fft(data((ii-1)*N+1 : ii*N))));
    end
end

function [freq_mean, freq_std] = get_fft_stats(data, Fs)
    L = length(data);
    f_shifted = (Fs/L)*(-L/2:L/2-1).';

    Y = fft(data);
    Y_shifted = fftshift(Y);
    
    Y_abs = abs(Y_shifted);
    Y_sum = sum(Y_abs);
    Y_scaled = Y_abs .* (1/Y_sum);
    Y_weighted_1 = Y_scaled .* f_shifted;

    freq_mean = sum(Y_weighted_1);
    Y_var = sum(Y_scaled .* (f_shifted - freq_mean).^2);

    freq_std = sqrt(Y_var);
end
