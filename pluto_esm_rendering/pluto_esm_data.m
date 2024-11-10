dwell_data_channel_peak = readmatrix('./dwell_data_channel_peak_1.3ghz_ant.txt');
dwell_data_channel_accum = readmatrix('./dwell_data_channel_accum_1.3ghz_ant.txt');
dwell_data_channel_duration = readmatrix('./dwell_data_channel_duration_1.3ghz_ant.txt');

dwell_data_channel_duration(dwell_data_channel_duration == 0) = 1;
%dwell_data_channel_accum(dwell_data_channel_accum == 0) = 0.001;

%dwell_data_channel_peak(:, 100:50:end) = 0;
%dwell_data_channel_accum(:, 100:50:end) = 0;

%d_accum_adj = (sqrt(dwell_data_channel_accum) ./ dwell_data_channel_duration) * 1e7;

dwell_data_channel_peak(dwell_data_channel_peak == 0) = 1;
d_peak_adj = 10*log10(dwell_data_channel_peak) * 10;

%d_accum_adj = 10*log10(dwell_data_channel_accum ./ dwell_data_channel_duration) + 130;
%d_accum_adj(d_accum_adj < -100) = -100;

d_accum_adj = 20*log10(dwell_data_channel_accum ./ dwell_data_channel_duration);
%d_accum_adj = dwell_data_channel_accum ./ dwell_data_channel_duration;

d_peak_to_avg = dwell_data_channel_peak ./ (dwell_data_channel_accum ./ dwell_data_channel_duration);
d_peak_to_avg(d_peak_to_avg == Inf) = 0;
d_peak_to_avg(dwell_data_channel_accum < 50) = 0;

d_peak_to_avg = 20*log10(d_peak_to_avg);
%max(dwell_data_channel_peak(:))
%mean(dwell_data_channel_peak(:))
%std(dwell_data_channel_peak(:))

%d_peak_adj = dwell_data_channel_peak ./ 5;
%d_peak_adj(d_peak_adj > 1) = 1;


%imshow(d_accum_adj, jet);
%imshow(d_peak_adj, jet);

%imagesc(d_accum_adj);
f = figure(1);
t = tiledlayout(2,1,'TileSpacing','Compact','Padding','Compact');
ax1 = nexttile
ax2 = nexttile
imagesc(ax1, d_peak_adj);
imagesc(ax2, d_peak_to_avg);
linkaxes([ax1, ax2], 'xy');