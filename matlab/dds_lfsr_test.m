filename = "lfsr_output.txt";

lines = readlines(filename);
input_i = [];
input_channel = [];
for ii = 1:length(lines)
    if strlength(lines(ii)) <= 1
        continue
    end    
    d = sscanf(lines(ii), "# %d");
    input_i = [input_i; d];
end


[c,lags] = xcorr(input_i);
figure(1);
stem(lags,c);
