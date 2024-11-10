dwell_data_channel_peak = readmatrix('./dwell_data_channel_peak_1.3ghz_ant.txt');
dwell_data_channel_accum = readmatrix('./dwell_data_channel_accum_1.3ghz_ant.txt');
dwell_data_channel_duration = readmatrix('./dwell_data_channel_duration_1.3ghz_ant.txt');

dwell_data_channel_duration = dwell_data_channel_duration * (0.5/61.44e6);

dwell_data_channel_peak(:, 100:50:end) = 0;
dwell_data_channel_accum(:, 100:50:end) = 0;

image_size = [size(dwell_data_channel_peak, 1), 600];

output_ratio = size(dwell_data_channel_peak, 2) / image_size(2);

output_accum = zeros(image_size);
output_peak = zeros(image_size);
for output_col = 0:(image_size(2)-1)
    input_col = [floor(output_col * output_ratio), floor((output_col + 1)*output_ratio) - 1];
    
    input_accum = dwell_data_channel_accum(:, (input_col(1) + 1):(input_col(2) + 1));
    input_peak = dwell_data_channel_peak(:, (input_col(1) + 1):(input_col(2) + 1));

    output_accum(:, output_col + 1) = sum(input_accum, 2);
    output_peak(:, output_col + 1) = sum(input_peak, 2);
end


f = figure(1);
t = tiledlayout(2,1,'TileSpacing','Compact','Padding','Compact');
ax1 = nexttile
ax2 = nexttile
imagesc(ax1, 10*log10(dwell_data_channel_peak));
imagesc(ax2, 10*log10(output_peak));
linkaxes([ax1, ax2], 'y');
