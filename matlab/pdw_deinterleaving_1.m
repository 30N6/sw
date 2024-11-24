max_pri = 14000e-6 * 4;
ts = 1/1.92e6;
max_pri_clks = max_pri / ts;
adjusted_max_pri_clks = 2^ceil(log2(max_pri_clks));
max_hist_length = 8192;
if adjusted_max_pri_clks > max_hist_length
    pri_bin_width = adjusted_max_pri_clks / max_hist_length; 
    hist_length = max_hist_length;
else
    pri_bin_width = 1;
    hist_length = adjusted_max_pri_clks;
end
pri_bin_ranges = 0:pri_bin_width:(adjusted_max_pri_clks - pri_bin_width);
pri_bin_centers = pri_bin_ranges + pri_bin_width/2;

for ii = 1:6
    td_n = td(:, ii) / 32;
    td_n = td_n(td_n ~= 0);
    pri_bin_counts = histc(td_n, pri_bin_ranges);
    
    %threshold (T) = x(E - c)e^(-T/(kN))
    p_x = 0.1;
    p_k = 3e-6;
    pri_threshold = p_x * (length(matching_pdws) - 1) * exp(-pri_bin_times ./ (p_k * length(pri_bin_times)));
    
    figure(1); 
    subplot(4,1,ii);
    hold off;
    bar(pri_bin_ranges * ts, pri_bin_counts, 'histc');
    hold on;
    plot(pri_bin_times, pri_threshold);
    hold off;
    
    figure(2); 
    subplot(4,1,ii);
    plot(td_n * ts, 'o');
end