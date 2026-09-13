%n = [0:31]';
n = [0:1023]';

W_fft8 = exp(-2j*pi*n/8);
W_fft16 = exp(-2j*pi*n/16);
W_fft32 = exp(-2j*pi*n/32);
W_fft64 = exp(-2j*pi*n/64);
W_fft128 = exp(-2j*pi*n/128);
W_fft256 = exp(-2j*pi*n/256);
W_fft512 = exp(-2j*pi*n/512);
W_fft1024 = exp(-2j*pi*n/1024);

% (a+bi) * (c+di) 
% k1 = c * (a+b)
% k2 = a * (d-c)
% k3 = b * (c+d)
% re = k1 - k3
% im = k1 + k2

total_bits = [23, 24, 24];
frac_bits  = [22, 22, 22];

disp("W_8");
calc_components_fixed(W_fft8, total_bits, frac_bits);

disp("W_16");
calc_components_fixed(W_fft16, total_bits, frac_bits);

disp("W_32");
calc_components_fixed(W_fft32, total_bits, frac_bits);

disp("W_64");
calc_components_fixed(W_fft64, total_bits, frac_bits);

disp("W_128");
calc_components_fixed(W_fft128, total_bits, frac_bits);

disp("W_256");
calc_components_fixed(W_fft256, total_bits, frac_bits);

disp("W_512");
calc_components_fixed(W_fft512, total_bits, frac_bits);

disp("W_1024");
calc_components_fixed(W_fft1024, total_bits, frac_bits);

function calc_components_fixed(W, total_bits, frac_bits)
    [c, d_minus_c, c_plus_d] = calc_components(W);
        
    s = "C: ";
    for ii = 1:length(c)
        v = round(c(ii) * 2^frac_bits(1));
        v_clipped = min(v, 2^(total_bits(1)-1) - 1);
        if (abs(v - v_clipped) > 0)
            fprintf("c clipped: ii=%d\n", ii);
        end
        s = strcat(s, sprintf("%d, ", v_clipped));
    end
    disp(s);

    s = "D_minus_C: ";
    for ii = 1:length(d_minus_c)
        v = round(d_minus_c(ii) * 2^frac_bits(2));
        v_clipped = min(v, 2^(total_bits(2)-1) - 1);
        if (abs(v - v_clipped) > 0)
            fprintf("d_minus_c clipped: ii=%d\n", ii);
        end
        s = strcat(s, sprintf("%d, ", v_clipped));
    end
    disp(s);    

    s = "C_plus_D: ";
    for ii = 1:length(c_plus_d)
        v = round(c_plus_d(ii) * 2^frac_bits(3));
        v_clipped = min(v, 2^(total_bits(3)-1) - 1);
        if (abs(v - v_clipped) > 0)
            fprintf("c_plus_d clipped: ii=%d\n", ii);
        end
        s = strcat(s, sprintf("%d, ", v_clipped));
    end
    disp(s);    
end

function [c, d_minus_c, c_plus_d] = calc_components(v)
    c = real(v);
    d = imag(v);
    d_minus_c = d - c;
    c_plus_d = c + d;
end