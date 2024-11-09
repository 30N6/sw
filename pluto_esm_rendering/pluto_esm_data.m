dwell_data_channel_peak = readmatrix('./dwell_data_channel_peak.txt');
dwell_data_channel_accum = readmatrix('./dwell_data_channel_accum.txt');
dwell_data_channel_duration = readmatrix('./dwell_data_channel_duration.txt');

dwell_data_channel_duration(dwell_data_channel_duration == 0) = 1;

%dwell_data_channel_peak(:, 100:50:end) = 0;
%dwell_data_channel_accum(:, 100:50:end) = 0;

%d_accum_adj = (sqrt(dwell_data_channel_accum) ./ dwell_data_channel_duration) * 1e7;

dwell_data_channel_peak(dwell_data_channel_peak == 0) = 1;
d_peak_adj = 10*log10(dwell_data_channel_peak) * 10;

%max(dwell_data_channel_peak(:))
%mean(dwell_data_channel_peak(:))
%std(dwell_data_channel_peak(:))

%d_peak_adj = dwell_data_channel_peak ./ 5;
%d_peak_adj(d_peak_adj > 1) = 1;


%imshow(d_accum_adj, jet);
imshow(d_peak_adj, jet);