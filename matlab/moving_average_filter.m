scale_factor = 0.00005;
data_len = 10000;

input_data = scale_factor * rand([data_len, 1]);
input_data = fi(input_data, 0, 16, 16);

input_data(500:2000) = input_data(500:2000) + 4*scale_factor;


filter_length = 32;
b = ones([filter_length, 1]);
moving_average_expected = conv(b, input_data) / length(b);

%% comb followed by integrator
output_ci_comb = fi(zeros([data_len, 1]), 0, 16, 16, 'OverflowAction', 'Wrap');
output_ci_int  = fi(zeros([data_len, 1]), 0, 16, 16, 'OverflowAction', 'Wrap');
for ii = (filter_length + 1):data_len
    output_ci_comb(ii) = input_data(ii) - input_data(ii - filter_length);
end
for ii = 2:data_len
    output_ci_int(ii) = output_ci_comb(ii) + output_ci_int(ii - 1);
    %simulate reset behavior
    %if ii == 1000
    %    output_ci_int(ii) = 0;
    %end    
end
output_ci_int = output_ci_int * (1/filter_length);

%% integrator followed by comb
output_ic_comb = fi(zeros([data_len, 1]), 0, 16, 16, 'OverflowAction', 'Wrap');
output_ic_int  = fi(zeros([data_len, 1]), 0, 16, 16, 'OverflowAction', 'Wrap');
for ii = 2:data_len
    output_ic_int(ii) = input_data(ii) + output_ic_int(ii - 1);
    %simulate reset behavior
    %if ii == 1000
    %    output_ic_int(ii:-1:(ii-128)) = 0;
    %end    
end
for ii = (filter_length + 1):data_len
    output_ic_comb(ii) = output_ic_int(ii) - output_ic_int(ii - filter_length);
end
output_ic_comb = output_ic_comb * (1/filter_length);


figure(1);
plot(1:length(input_data), input_data, ...
     1:length(moving_average_expected), moving_average_expected, '-o',...
     1:length(output_ic_int), output_ic_comb, '-+');