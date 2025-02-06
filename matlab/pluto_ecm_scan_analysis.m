%filename = "analysis-20250205-171622.log";
%filename = "analysis-20250205-210734-ntsc-5917-dark-20mw-far.log";
%filename = "analysis-20250205-210851-ntsc-5917-dark-bright-20mw-far.log";
%filename = "analysis-20250205-225643-915.log";
filename = "analysis-20250205-232443-arsr-4.log";

Fs = 7.68e6;
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
        scan_reports(ii).iq_data = scan_reports(ii).iq_data - mean(scan_reports(ii).iq_data) * 1.0; %0.999;
        if (mod(scan_reports(ii).channel_index, 2) == 1)
            scan_reports(ii).iq_data = baseband(scan_reports(ii).iq_data);
        end
        
        scan_reports(ii).iq_data = paddata(scan_reports(ii).iq_data, L);
    end

    scan_reports = scan_reports';
end


%filter_freq = 5665;
%filter_freq = 5715;
%filter_freq = 5925;
filter_freq = 1325;

filtered_reports = scan_reports([scan_reports.dwell_freq] == filter_freq);


channel_count = zeros(16, 1);
for ii = 1:length(filtered_reports)
    channel_count(filtered_reports(ii).channel_index + 1) = channel_count(filtered_reports(ii).channel_index + 1) + 1;
end

max_channel_count = min(channel_count(3:15))
current_channel_count = zeros(13, 1);
reports_by_channel = repmat(filtered_reports(1), max_channel_count, 13);

for ii = 1:length(filtered_reports)
    r = filtered_reports(ii);
    chan_m = r.channel_index - 1;
    reports_by_channel(current_channel_count(chan_m) + 1, chan_m) = r;
    current_channel_count(chan_m) = current_channel_count(chan_m) + 1;
end


%%
figure(1);

num_rows = 4;
ax = zeros(4, 13);
for row = 1:num_rows
    for col = 1:13
        plot_index = (row-1) * 13 + col;
        ax(row, col) = subplot(num_rows,13,plot_index);
        
        d = reports_by_channel(row, col);

        Y = fft(d.iq_data);
        %plot(Fs/L*(-L/2:L/2-1), 20*log10(abs(fftshift(Y))),"LineWidth",1)
        plot(Fs/L*(-L/2:L/2-1), (abs(fftshift(Y))),"LineWidth",1)

        channel_freq = d.dwell_freq + (Fs/2)/1e6 * (d.channel_index - 8);

        s = sprintf("%d %d: %.1f", d.dwell_freq, d.channel_index, channel_freq);
        title(s);
        xlabel("f (Hz)");
        ylabel("|fft(X)|");
    end
end
%linkaxes(ax, 'y');


%%
r = 10;
c = 10;
d = reports_by_channel(r, c);

figure(2);
ax_1 = subplot(6,1,1);
t = [(0:L-1) / Fs].' * 1e6;
plot(t, real(d.iq_data), t, imag(d.iq_data));

ax_2 = subplot(6,1,2);
instfreq(d.iq_data, Fs);
linkaxes([ax_1, ax_2], 'x');

subplot(6,1,3);
[c,lags] = xcorr(d.iq_data);
plot(lags * (1/Fs) * 1e6, (abs(c)));

subplot(6,1,4); 
X = fft(d.iq_data);
xc = abs(ifft(X .* conj(X)));

tx = t(1:L/2);
xc = xc(1:L/2);

m_xc = mean(xc);
s_xc = std(xc) * 1.0;

i_th = xc > (m_xc + s_xc);
xc_th = xc(i_th);
t_th = tx(i_th);

plot(tx, xc, [0, tx(end)], [m_xc, m_xc], [0, tx(end)], [m_xc + s_xc, m_xc + s_xc], t_th, xc_th, 'o');

subplot(6,1,5);
sf = compute_sfft(d.iq_data, 32);
imagesc(sf.');

subplot(6,1,6);
Y = fft(d.iq_data);
%plot(Fs/L*(-L/2:L/2-1), 20*log10(abs(fftshift(Y))),"LineWidth",1)
plot(Fs/L*(-L/2:L/2-1), (abs(fftshift(Y))),"LineWidth",1)

fprintf("corr ratio: %f\n", s_xc/m_xc);


%%
function r = compute_sfft(data, N)
    r = zeros(length(data)/N, N);
    for ii = 1:(length(data)/N)
        r(ii, :) = abs(fft(data((ii-1)*N+1 : ii*N)));
    end
end

function r = baseband(data)
    b = ones(length(data), 1);
    b(1:2:end) = -1;
    r = data .* b;
end
