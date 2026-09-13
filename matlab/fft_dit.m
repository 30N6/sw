
N           = 1024;
mag         = rand(N, 1);
phase       = rand(N, 1) * 2*pi - pi;
[re, im]    = pol2cart(phase, mag);
d           = re + im*1i;
    
if N == 2
    fft_2(d);
elseif N == 4
    fft_4(d);
else
    [X, idx] = fft_radix2_DIT(d);
end

%idx - 1
fprintf('(');
for ii = 1:N
    fprintf('%d', idx(ii) - 1);
    if ii == N
        fprintf(')\n');
    else
        fprintf(', ');
    end
end

function [X, idx] = fft_radix2_DIT(x)
    N = length(x);
    X = zeros(N, 1);
    
    i_e = (1:2:N-1)';
    i_o = (2:2:N)';

    x_e = x(i_e);
    x_o = x(i_o);
    
    if (N > 8)
        [E_x, E_i] = fft_radix2_DIT(x_e);
        [O_x, O_i] = fft_radix2_DIT(x_o);
        idx = [i_e(E_i); i_o(O_i)];
    elseif (N == 8)
        E_x = fft_4(x_e);
        O_x = fft_4(x_o);
        idx = [i_e; i_o];
    end
    
    n = 0:(N/2-1);
    W = exp(-2j*pi*n/N);

    for ii = 1:(N/2)
        p = E_x(ii);
        q = W(ii) * O_x(ii);
        X(ii) = p + q;
        X(ii + N/2) = p - q;
    end

    X_m = fft(x);
    assert(sum(abs(X - X_m)) < 0.001);
end

function X = fft_4(x)
    X = zeros(4, 1);
    X(1) = x(1) + x(2) + x(3) + x(4);
    X(2) = x(1) - 1j*x(2) -x(3) + 1j*x(4);
    X(3) = x(1) - x(2) + x(3) - x(4);
    X(4) = x(1) + 1j*x(2) - x(3) - 1j*x(4);

    X_m = fft(x);
    assert(sum(abs(X - X_m)) < 0.001);
end

function X = fft_2(x)
    %fft(x)
    X = [x(1) + x(2); x(1) - x(2)];

    X_m = fft(x);
    assert(sum(abs(X - X_m)) < 0.001);
end