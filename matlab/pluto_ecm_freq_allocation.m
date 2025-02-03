freq_a      = [5725, 5745, 5765, 5785, 5805, 5825, 5845, 5865];
freq_b      = [5733, 5752, 5771, 5790, 5809, 5828, 5847, 5866];
freq_e      = [5645, 5665, 5685, 5705, 5885, 5905, 5925, 5945];
freq_f      = [5740, 5760, 5780, 5800, 5820, 5840, 5860, 5880];
freq_r      = [5658, 5695, 5732, 5769, 5806, 5843, 5880, 5917];
freq_dji    = [5660, 5695, 5735, 5770, 5805, 5839, 5878, 5914];

freqs = {freq_a, freq_b, freq_e, freq_f, freq_r, freq_dji};
bw = 4;

dwell_freq = [5665, 5715, 5765, 5815, 5865, 5925];
dwell_bw = 50;    

figure(1);
hold off;
% 
% X1 = rand(1, 10);
% X2 = rand(1, 10);
% Y1 = rand(1, 10);
% Y2 = rand(1, 10);
% subplot(1,2,1)
% plot([X1; X2], [Y1; Y2])      % A bunch of separate lines
% 
% return

freq_x = zeros(2, 0);
freq_y = zeros(2, 0);

for ii = 1:length(freqs)
    freq_1 = freqs{ii} - bw/2;
    freq_2 = freqs{ii} + bw/2;
    freq_x = [freq_x, [freq_1; freq_2]];
    freq_y = [freq_y, ones(2, size(freqs{ii}, 2)) * ii];
end

plot(freq_x, freq_y, 'o-');
hold on;

for ii = 1:length(dwell_freq)
    f_1 = dwell_freq(ii) - dwell_bw/2;
    f_2 = dwell_freq(ii) + dwell_bw/2;

    plot([f_1, f_1], [0.5, length(freqs) + 0.5]);
    plot([f_2, f_2], [0.5, length(freqs) + 0.5]);
end