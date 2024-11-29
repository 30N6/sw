%pulse_iq = [[-2, -1], [1, -1], [1, 1], [-1, 0], [0, -1], [1, 0], [-3, 0], [-3, -4], [2, -3], [2, 3], [-4, 2], [-3, -4], [4, -3], [3, 5], [-4, 3], [-3, -5], [4, -5], [4, 1], [-2, 3], [-5, -1], [-3, -6], [4, -6], [7, 2], [0, 6], [-7, 3], [-5, -5], [2, -8], [6, -2], [5, 3], [0, 6], [-6, 4], [-8, -2], [-4, -6], [2, -6], [4, -4], [5, -1], [4, 4], [0, 6], [-5, 5], [-7, 1], [-6, -1], [-6, -3], [-5, -6], [-3, -7], [1, -5], [4, -4], [6, -2], [6, -1], [0, 0], [0, 0]];
%pulse_iq = [[-10, -7], [-15, -2], [-16, 0], [3, -6], [14, -7], [0, 2], [-5, 10], [9, 15], [8, 10], [-5, -3], [-13, -3], [-16, 8], [-8, 5], [2, -9], [1, -15], [-4, -11], [-10, -7], [-18, -5], [-4, -4], [17, -4], [7, 2], [-11, 10], [-6, 2], [-2, -11], [-10, -10], [-11, -4], [-13, 1], [-14, 2], [0, -6], [11, -9], [3, 8], [-5, 14], [-7, -6], [-5, -13], [4, 2], [12, 0], [13, -14], [7, -7], [-4, 13], [-6, 8], [-2, -9], [-10, -9], [-18, -2], [-5, -2], [9, -5], [7, -10], [1, -14], [-2, -12], [0, 0], [0, 0]];
pulse_iq = [[0, -3], [-4, -1], [2, 3], [4, -5], [-7, -2], [3, 9], [9, -7], [-10, -10], [-4, 11], [17, 1], [-2, -18], [-20, 5], [7, 20], [22, -9], [-9, -25], [-25, 4], [0, 24], [21, 6], [10, -19], [-12, -17], [-17, 4], [-4, 16], [10, 11], [15, -1], [9, -10], [-3, -13], [-10, -9], [-12, -2], [-11, 4], [-7, 10], [-1, 14], [5, 14], [10, 10], [16, 6], [20, 0], [22, -6], [21, -9], [20, -14], [19, -19], [20, -22], [22, -21], [23, -20], [24, -19], [27, -17], [31, -10], [34, 1], [31, 11], [23, 21], [0, 0], [0, 0]]

pulse_iq = pulse_iq(1:2:end) + 1j * pulse_iq(2:2:end);

figure(1);
subplot(3, 1, 1);
plot(1:length(pulse_iq), real(pulse_iq), 1:length(pulse_iq), imag(pulse_iq), 1:length(pulse_iq), abs(pulse_iq));


valid_pulse_iq = pulse_iq(9:end-2);

phase = unwrap(atan2(imag(valid_pulse_iq), real(valid_pulse_iq)));
freq = (1/(2*pi)) * diff(phase) / dt;

x_phase = (0:length(phase)-1) * dt;
[p_p, S_phase] = polyfit(x_phase, phase, 2);
ss_res = S_phase.normr ^ 2;
ss_tot = sum((freq - mean(freq)).^2);
r_squared_phase = 1 - ss_res/ss_tot;
p_phase = p_p(1) * (x_phase.^2) + p_p(2) * x_phase + p_p(3);

x_freq = (0:length(freq)-1) * dt;
[p_f, S_freq] = polyfit(x_freq, freq, 1);
ss_res = S_freq.normr ^ 2;
ss_tot = sum((freq - mean(freq)).^2);
r_squared_freq = 1 - ss_res/ss_tot;
p_freq = p_f(1) * x_freq + p_f(2);

fprintf("normr=%f %f  r_squared=%f %f  snr=%f snr=%f -- slope: %f %f \n", S_phase.normr/ length(x_phase), S_freq.normr / length(x_freq), r_squared_phase, r_squared_freq, ...
    pdw.implied_pulse_snr, pdw.recorded_pulse_snr, 2*p_p(1) * (1/(2*pi)), p_f(1));

subplot(3,1,2);
plot(x_phase, phase, x_phase, p_phase);

subplot(3,1,3);
plot(x_freq, freq, x_freq, p_freq);

r_freq = freq - p_freq;