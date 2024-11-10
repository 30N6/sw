figure(2); 
%plot(dwell_data_channel_accum(:, 1393)); hold on; 
%plot(dwell_data_channel_accum(:, 1392)); 
%plot(dwell_data_channel_accum(:, 1391));
%plot(dwell_data_channel_accum(:, 1390));
%
%figure(3); 
%plot(dwell_data_channel_peak(:, 1393)); hold on; 
%plot(dwell_data_channel_peak(:, 1392)); 
%plot(dwell_data_channel_peak(:, 1391));
%plot(dwell_data_channel_peak(:, 1390));
%

peak_to_accum = dwell_data_channel_peak ./ dwell_data_channel_accum;
peak_to_accum(peak_to_accum == Inf) = 0;
imagesc(peak_to_accum);