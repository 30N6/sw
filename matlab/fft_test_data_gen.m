N = 1024;
reverse = 0;

if (reverse)
    d = "reverse";
else
    d = "forward";
end
filename_base = sprintf("fft_test_data_2026_09_12_%d_%s", N, d);

fd_in = fopen(filename_base + "_in.txt", "w");
fd_out = fopen(filename_base + "_out.txt", "w");

rng("default");

input_width = 16;
output_width = 21;

for frame = 1:100
    %x = gen_fft_input(N);
    x = gen_fft_input_fixed(N, input_width, frame);
    %X = fft(x);
    if (reverse)
        X = N*ifft(x);
    else
        X = fft(x);
    end
    
    %{
    input_order = [0 8 16 24 4 12 20 28 2 10 18 26 6 14 22 30   1 9 17 25 5 13 21 29 3 11 19 27 7 15 23 31];
    input_data = zeros(N, 2);
    X_full_fft4 = zeros(N, 1);
    X_full_fft8 = zeros(N, 1);
    X_full_fft16 = zeros(N, 1);
    X_full_fft32 = zeros(N, 1);

    if (frame == 9)
        disp("");
    end

    for jj = 1:8
        x_fft4 = x(input_order(4*(jj-1)+1 : 4*(jj-1)+4) + 1);
        X_fft4 = fft(x_fft4);

        x_scaled_fft4 = [round(real(x_fft4)), round(imag(x_fft4))];
        X_scaled_fft4 = [round(real(X_fft4)), round(imag(X_fft4))];

        X_full_fft4(4*(jj-1)+1 : 4*(jj-1)+4) = X_fft4;
    end

    X_scaled_fft4 = [round(real(X_full_fft4)), round(imag(X_full_fft4))];

    W_fft8 = exp(-2j*pi*(0:3)/8);
    for ii = 1:(N/8)
        E_in = X_full_fft4((8*(ii-1) + 1):(8*(ii-1) + 4));
        O_in = X_full_fft4((8*(ii-1) + 5):(8*(ii-1) + 8));
        for jj = 1:4
            p = E_in(jj);
            q = W_fft8(jj) * O_in(jj);
            X_full_fft8(8*(ii-1) + jj) = p + q;
            X_full_fft8(8*(ii-1) + jj + 4) = p - q;
        end
    end    
    X_scaled_fft8 = [round(real(X_full_fft8)), round(imag(X_full_fft8))];

    W_fft16 = exp(-2j*pi*(0:7)/16);
    for ii = 1:(N/16)
        E_in = X_full_fft8((16*(ii-1) + 1):(16*(ii-1) + 8));
        O_in = X_full_fft8((16*(ii-1) + 9):(16*(ii-1) + 16));
        for jj = 1:8
            p = E_in(jj);
            q = W_fft16(jj) * O_in(jj);
            X_full_fft16(16*(ii-1) + jj) = p + q;
            X_full_fft16(16*(ii-1) + jj + 8) = p - q;
        end
    end
    X_scaled_fft16 = [round(real(X_full_fft16)), round(imag(X_full_fft16))];

    W_fft32 = exp(-2j*pi*(0:15)/32);
    E_in = X_full_fft16(1:16);
    O_in = X_full_fft16(17:32);
    for jj = 1:16
        p = E_in(jj);
        q = W_fft32(jj) * O_in(jj);
        X_full_fft32(jj) = p + q;
        X_full_fft32(jj + 16) = p - q;
    end    
    X_scaled_fft32 = [round(real(X_full_fft32)), round(imag(X_full_fft32))];

    %for jj = 1:4
    %    x_fft8 = x(input_order(8*(jj-1)+1 : 8*(jj-1)+8) + 1);
    %    X_fft8 = fft(x_fft8);
    %
    %    x_scaled_fft8 = [round(real(x_fft8)), round(imag(x_fft8))];
    %    X_scaled_fft8 = [round(real(X_fft8)), round(imag(X_fft8))];
    %end
    %}


    tx_data = [x, (0:N-1)'];
    tx_shuffled = tx_data(randperm(N), :);
    for jj = 1:N
        fprintf(fd_in, "%02d %02d %d %d %d\n", frame, uint32(tx_shuffled(jj, 2)), uint32(jj == N), real(tx_shuffled(jj, 1)), imag(tx_shuffled(jj, 1)));
    end
    for jj = 1:N
        fprintf(fd_out, "%02d %02d %d %10d %10d\n", frame, jj-1, uint32(jj == N), round(real(X(jj))), round(imag(X(jj))));
    end    
end

fclose(fd_in);
fclose(fd_out);

function r = float_to_fixed(v, w, clip)
    r = v * 2^(w - 1);
    if clip
        r = min(r, 2^(w - 1) - 1);
    end
    r = round(r);    
end

function d = gen_fft_input_fixed(N, width, frame)
    %re = randi([-2^(width-1), 2^(width-1) - 1], N, 1);
    %im = randi([-2^(width-1), 2^(width-1) - 1], N, 1);
    if (frame == 1)
        re = ones(N, 1) * 2^(width-1) - 1;
        im = ones(N, 1) * 2^(width-1) - 1;
    elseif (frame == 2)
        re = zeros(N, 1);
        im = zeros(N, 1);
    else
        re = randi([-2^(width-1), 2^(width-1) - 1], N, 1);
        im = randi([-2^(width-1), 2^(width-1) - 1], N, 1);            
    end
    
    d = re + 1j*im;
end

function d = gen_fft_input(N)
    mag         = rand(N, 1);
    phase       = rand(N, 1) * 2*pi - pi;
    [re, im]    = pol2cart(phase, mag);
    d           = re + im*1i;
end