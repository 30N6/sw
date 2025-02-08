filename = "analysis-20250207-180714-elrs-F1000.log";

Fs = 7.68e6;
dt = 1/Fs;
L = 2048;

reload = 0;

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
        scan_reports(ii).mean_power_dB = 20*log10(mean(abs(scan_reports(ii).iq_data)));
        scan_reports(ii).iq_data_padded = paddata(scan_reports(ii).iq_data, L);        

        scan_reports(ii).iq_phase = unwrap(atan2(imag(scan_reports(ii).iq_data), real(scan_reports(ii).iq_data)));
        scan_reports(ii).iq_freq = (1/(2*pi)) * diff(scan_reports(ii).iq_phase) / dt;        
        scan_reports(ii).timestamp_sec = scan_reports(ii).timestamp * (1/(4*61.44e6));

        if length(scan_reports(ii).iq_freq) < 50
            scan_reports(ii).r_squared_fsk_min = 0;
            scan_reports(ii).r_squared_fsk_max = 0;
        else
            l_freq = length(scan_reports(ii).iq_freq);
            rs = [analyze_fsk(scan_reports(ii).iq_freq(1:floor(l_freq/2)), 2, Fs), analyze_fsk(scan_reports(ii).iq_freq(ceil(l_freq/2):end), 2, Fs)]
            scan_reports(ii).r_squared_fsk_min = min(rs);
            scan_reports(ii).r_squared_fsk_max = max(rs);
        end
    end

    scan_reports = scan_reports';
end


freqs = unique([scan_reports.dwell_freq]);
figure(10);
for ii = 1:length(freqs)
    subplot(length(freqs), 1, ii)
    r = scan_reports([scan_reports.dwell_freq] == freqs(ii));
    plot([r.timestamp] * (1/(4*61.44e6)), [r.mean_power_dB], 'o');
end

freqs = unique([scan_reports.dwell_freq]);
figure(11);
for ii = 1:length(freqs)
   subplot(length(freqs), 1, ii)
   r = scan_reports([scan_reports.dwell_freq] == freqs(ii));
   plot([r.timestamp] * (1/(4*61.44e6)), [r.r_squared_fsk_min], 'o', [r.timestamp] * (1/(4*61.44e6)), [r.r_squared_fsk_max], 'o');
end


filter_freq = 2475;

is_tx_listen = false(length(scan_reports), 1);
for ii = 1:length(scan_reports)
    is_tx_listen(ii) = scan_reports(ii).controller_state == "TX_LISTEN";
end
freq_match      = ([scan_reports.dwell_freq] == filter_freq).';
length_match    = ([scan_reports.iq_length] > 128).';
power_match     = ([scan_reports.mean_power_dB] > 10).';
timestamp_match = ([scan_reports.timestamp_sec] > 11).' & ([scan_reports.timestamp_sec] < 100).';
mod_match        = ([scan_reports.r_squared_fsk_max] > 0.7).';
filtered_reports = scan_reports(freq_match & length_match & is_tx_listen & power_match & timestamp_match & mod_match);

figure(20);
subplot(3,1,1);
%plot([filtered_reports.mean_power_dB]);
%plot([filtered_reports.timestamp] * (1/(4*61.44e6)), [filtered_reports.mean_power_dB], 'o');
plot([filtered_reports.mean_power_dB], 'o');
subplot(3,1,2);
plot([filtered_reports.iq_length], [filtered_reports.mean_power_dB], 'o');

%%
offset = 0;
num_rows = 6;
num_cols = 6;

figure(2);
ax1 = zeros(num_rows, num_cols);
figure(3);
ax2 = zeros(num_rows, num_cols);

for row = 1:num_rows
    for col = 1:num_cols
        plot_index = (row-1) * num_cols + col;
        d = filtered_reports(plot_index + offset);        

        channel_freq = d.dwell_freq + (Fs/2)/1e6 * (d.channel_index - 8);
        s = sprintf("[%d] %d %d: %.1f %0.3f %0.3f", plot_index + offset, d.dwell_freq, d.channel_index, channel_freq, d.r_squared_fsk_max, d.r_squared_fsk_min);
        
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
        s = sprintf("[%d] %d %d: %.1f %0.3f %0.3f", plot_index + offset, d.dwell_freq, d.channel_index, channel_freq, d.r_squared_fsk_max, d.r_squared_fsk_min);
        
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
d = filtered_reports(11);

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

m_xc = mean(xc);
s_xc = std(xc) * 1.0;

i_th = xc > (m_xc + s_xc);
xc_th = xc(i_th);
t_th = tx(i_th);

plot(tx, xc, [0, tx(end)], [m_xc, m_xc], [0, tx(end)], [m_xc + s_xc, m_xc + s_xc], t_th, xc_th, 'o');

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

freq_diff = diff(d.iq_freq);
freq_diff_clipped = freq_diff;
freq_diff_clipped(freq_diff_clipped > 1e5) = 0;
freq_diff_clipped(freq_diff_clipped < -1e5) = 0;

subplot(rows,2,9);
plot(t(1:end-2), freq_diff)

subplot(rows,2,10);
plot(t(1:end-2), freq_diff_clipped);

subplot(rows,2,11);
plot(t(1:end-2), cumsum(freq_diff_clipped));

subplot(rows, 2, 12);
plot(filter(ones(16,1), 1, d.iq_freq));

fprintf("corr ratio: %f\n", s_xc/m_xc);


%%
function r = compute_sfft(data, N)
    r = zeros(length(data)/N, N);
    for ii = 1:(length(data)/N)
        r(ii, :) = fftshift(abs(fft(data((ii-1)*N+1 : ii*N))));
    end
end


function r_squared = analyze_fsk(data, M, Fs)
    freq_mean = mean(data);

    freq_cluster = ones([length(data), 1]);
    freq_cluster(data >= freq_mean) = 2;
    
    %freq_sorted = sort(data.iq_freq);
    %freq_span = freq_sorted(round(length(freq_sorted) * 0.9)) - freq_sorted(round(length(freq_sorted) * 0.1));
    %freq_transitions = (data.iq_freq < (freq_mean + 0.8*freq_span/2)) & (data.iq_freq > (freq_mean - 0.8*freq_span/2));
    %freq_cluster(freq_transitions) = 0;
    
    ss_res = [0, 0];
    cluster_y = [0, 0];
    
    for ii = 1:M
        y_k = data(freq_cluster == ii);
        cluster_y(ii) = mean(y_k); %median(y_k);
        ss_res(ii) = sum((y_k - cluster_y(ii)).^2);
    end
    y_tot = data(freq_cluster ~= 0);
    ss_tot = sum((y_tot - mean(y_tot)).^2);
    
    r_squared = 1 - sum(ss_res) / ss_tot;
end

