iq_width = 12;
N = 1024;

%f = linspace(0, pi, N);
f = 0:pi/N:(pi - pi/N);

data_i = sin(f) * (2^(iq_width-1) - 1)/(2^(iq_width-1));
data_q = cos(f) * (2^(iq_width-1) - 1)/(2^(iq_width-1));

figure(1);
plot(f, data_i, f, data_q);

quantized_data_i = fi(data_i, 1, iq_width, iq_width - 1);
quantized_data_q = fi(data_q, 1, iq_width, iq_width - 1);

plot(f, quantized_data_i, f, quantized_data_q);



%%

s = "";
for ii = 1:N
    d_i = quantized_data_i(ii);
    d_q = quantized_data_q(ii);
    
    s = s + sprintf('%4d => \"%s%s\", ', ii - 1, d_q.bin, d_i.bin);
    if mod(ii-1, 8) == 7
        s = s + "\n";
    end
end
s = s + "\n";
fprintf(s)
