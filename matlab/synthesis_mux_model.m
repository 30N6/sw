filename = "mux_input.txt";

lines = readlines(filename);
input_i = [];
input_channel = [];
for ii = 1:length(lines)
    if strlength(lines(ii)) <= 1
        continue
    end    
    d = sscanf(lines(ii), "# %d %x");
    input_channel = [input_channel; d(1)];
    f = fi(0, 1, 28, 0);
    f.dec = string(d(2));
    input_i = [input_i; f];
end

L = 16;
num_frames = length(input_i) / L;

d = reshape(input_i, [L, num_frames]);

r = synthesis_mux(L, d);


function r = synthesis_mux(L, d)
    output_len = size(d, 2) * L / 2;
    r = zeros([1, output_len]);

    padded_d = [zeros(L, 1), d];
    
    a = padded_d(1:L/2, 1:size(d, 2));
    b = d(L/2+1:end, :);

    summed_d = a + b;

    i_row = mod([output_len-1:-1:0], L/2) + 1;
    %i_row = mod([0:output_len-1], L) + 1;
    i_col = floor((0:(output_len-1)) / (L/2)) + 1;
    
    ii = sub2ind(size(summed_d), i_row, i_col);

    r = summed_d(ii);
end