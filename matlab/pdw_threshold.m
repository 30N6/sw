ts = 1/1.92e6;
t = [0:ts:50e-3].';

amp_noise = 0.1;
amp_cw = 2;

y_noise = amp_noise * randn([length(t), 1]) + 1j * amp_noise * randn([length(t), 1]);
y_cw = amp_cw * exp(1j*2*pi*100e3*t);

pulse_freq = [500e3, -100e3];
pulse_prf = [300, 50];
pulse_amp = [20, 3];

y_pulse_1 = pulse_amp(1) * (cos(2*pi*pulse_prf(1)*t + pi/2) > 0.95) .* exp(1j*2*pi*pulse_freq(1)*t);
y_pulse_2 = pulse_amp(2) * (cos(2*pi*pulse_prf(2)*t + pi/2) > -0.5) .* exp(1j*2*pi*pulse_freq(2)*t);

y = y_noise + y_cw + y_pulse_1 + y_pulse_2;
p = abs(y);

threshold = zeros([length(t), 1]);
accum_value = 0;
accum_length = 0;
accum_points = 2.^[7:32];
for ii = 1:length(t)
    accum_value = accum_value + p(ii);
    accum_length = accum_length + 1;
    
    if ii > 1
        threshold(ii) = threshold(ii - 1);
    end
    
    if mod(accum_length, accum_points(1)) == 0
        for jj = 1:length(accum_points)
            if accum_length == accum_points(jj)
                threshold(ii) = accum_value / accum_points(jj);
                if jj == length(accum_points)
                    accum_length = 0;
                    accum_value = 0;
                end                
            end
        end
    end
end


figure(1);
%plot(t, real(y), t, imag(y), t, p, t, threshold);
plot(1:length(t), real(y), 1:length(t), imag(y), 1:length(t), p, 1:length(t), threshold);
%plot(t, y);