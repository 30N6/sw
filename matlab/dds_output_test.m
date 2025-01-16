filename = "dds_output.txt";
fs_in = 7.68e6;
L = 16;

reload = 0;

if reload
    lines = readlines(filename);
    input_data = zeros(length(lines), 3);
    
    for ii = 1:length(lines)
        if strlength(lines(ii)) <= 1
            continue
        end    
        d = sscanf(lines(ii), "# %d %d %d");
        dt =  d.';
        input_data(ii, :) = dt;
    end

    d_c = zeros(length(input_data)/L, L);
    
    for ii = 1:L
        d = input_data(input_data(:, 1) == (ii-1), 2:3);
        d_c(:, ii) = d(:, 1) + 1j * d(:, 2);
    end    
end

% figure(1);
% for ii = 1:L
%     subplot(sqrt(L), sqrt(L), ii);
%     instfreq(d_c(:, ii), fs_in);
% end
% 
% figure(2);
% for ii = 1:L
%     subplot(sqrt(L), sqrt(L), ii);
% 
%     M = 256;
%     g = hann(M,"periodic");
%     ov = 0.75*M;
%     Ndft = 256;    
% 
%     spectrogram(d_c(:, ii), g, ov, Ndft, fs_in, "centered");
% end

figure(2);
for ii = 1:L
    subplot(sqrt(L), sqrt(L), ii);
    
    Y = fft(d_c(:, ii));
    n = length(d_c(:, ii));
    
    plot(fs_in/n*(-n/2:n/2-1),20*log10(abs(fftshift(Y))));
    xlabel("f (Hz)")
    ylabel("|fft(X)|")
end