L = 16; % subbands

output_width = 12 + log2(L);

M = 10; % taps per subband
N = M*L; % total taps
alpha = 0.8; %0.85;        %broadening factor
beta = 0.8;                %shape factor
H = kaiser(N,beta*M)' .* sinc(((-N/2:N/2-1))/(alpha*L));
figure(1);
plot(H);
grid on;
title('Impulse response');

figure(2);
%w = linspace(0, 1, 1e3)'; h = freqz(H, length(w), w);
%plot(w, 10*log10(abs(h)));
freqz(H./sum(H))


K = L;
H_k = zeros(K, length(H));
n = 0:(length(H)-1);
f = linspace(-30.72e6, 30.72e6, 5e3);
h = zeros(K, length(f));
fs = 61.44e6;

for k=0:(K-1)
    kn = k - K/2;
    w_0 = kn*(1/K)*2*pi;

    %H_k(k+1, :) = 2*cos(w_0*n) .* H;
    H_k(k+1, :) = exp(-j*w_0*n) .* H .* (1/sum(H));

    h(k+1, :) = freqz(H_k(k+1, :), 1, f, fs);
end

figure(3);
plot(f, 20*log10(abs(h)));
grid on;
xlabel('Frequency (Hz)');
ylabel('Response (dB)');
title('Filter bank frequency response');

%%

H_s = zeros(L, N/L);
for ii = 1:L
    idx = ii:L:N;
    H_s(ii, :) = H(idx);
end

H_s_f = round(H_s * (2^(output_width - 1)));
H_f = round(H * (2^(output_width - 1)));
H_f(H_f > (2^(output_width - 1) - 1)) = 2^(output_width - 1) - 1;

%figure(3);
%plot(H - H_f / (2^(output_width - 1)));
s = "";
for ii = 1:length(H_f)
    s = s + sprintf('%3d => \"%s\", ', ii - 1, dec2bin(H_f(ii), output_width));
    if mod(ii-1, 8) == 7
        s = s + "\n";
    end
end
s = s + "\n";
fprintf(s)

s = "";
for ii = 1:length(H_f)
    s = s + sprintf("%3d: %d\'h%s, ", ii - 1, output_width, dec2hex(H_f(ii), ceil(output_width/4)));
    if mod(ii-1, 8) == 7
        s = s + "\n";
    end
end
s = s + "\n";
fprintf(s)

%
figs_to_save = [1, 2, 3];
for ii = 1:length(figs_to_save)
    fig_index = figs_to_save(ii);
    f = figure(fig_index);
    f.Position = [1400 100 800 500];
    %fig_filename = sprintf('%s_fig_%d.png', filename_base, fig_index);
    %saveas(f, fig_filename);
end
