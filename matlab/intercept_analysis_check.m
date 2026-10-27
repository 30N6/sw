%filename = "analysis-20261015-174144.log";
%filename = "analysis-20261015-232905.log";
%filename = "analysis-20261019-141746.log";
%filename = "analysis-20261018-232832-fsk-burst.log";
filename = "analysis-20261024-224447.log";

reload = 0;

if reload
    lines = readlines(filename);
    
    input_data = struct();
    features = struct()
    num_elements = 0;
    
    for ii = 1:length(lines)-1
        line_data = jsondecode(lines(ii));
        if ~isfield(line_data.data, "signal_analysis")
            continue;
        end

        line_data = line_data.data.signal_analysis;

        num_elements = num_elements + 1;
        if num_elements == 1
            input_data = line_data;
            features = line_data.features;
        else
            input_data(num_elements) = line_data;
            features(num_elements) = line_data.features;
        end
%
        %input_data(num_elements).stream_index   = line_data.data.stream_index;
        %input_data(num_elements).channel_index  = line_data.data.channel_index;
        %input_data(num_elements).lo_index       = line_data.data.lo_index;
        %input_data(num_elements).lo_frequency   = line_data.data.lo_freq;
        %input_data(num_elements).frequency      = dwell_frequency + (line_data.data.channel_index - 256) * (61.44/512);
        %input_data(num_elements).u_iq           = line_data.data.data_uI + 1j * line_data.data.data_uQ;
        %input_data(num_elements).d_iq           = line_data.data.data_dI + 1j * line_data.data.data_dQ;
        %
        %input_data(num_elements).fft_data_u       = fftshift(fft(input_data(num_elements).u_iq));
        %input_data(num_elements).fft_power_u      = abs(input_data(num_elements).fft_data_u).^2;
        %input_data(num_elements).fft_power_u_dB   = 10*log10(input_data(num_elements).fft_power_u);
%
        %input_data(num_elements).fft_data_d       = fftshift(fft(input_data(num_elements).d_iq));
        %input_data(num_elements).fft_power_d      = abs(input_data(num_elements).fft_data_d).^2;
        %input_data(num_elements).fft_power_d_dB   = 10*log10(input_data(num_elements).fft_power_d);        
    end
    
    for ii = 1:length(input_data)
        input_data(ii).iq_data        = input_data(ii).iq_data_I + 1j * input_data(ii).iq_data_Q;
        input_data(ii).fft_data       = fftshift(fft(input_data(ii).iq_data));
        input_data(ii).fft_power      = abs(input_data(ii).fft_data).^2;
        input_data(ii).fft_power_dB   = 10*log10(input_data(ii).fft_power);    
        input_data(ii).iq_amplitude   = abs(input_data(ii).iq_data);
    end
end

%%

%filtered_data = input_data([input_data.frequency] == analysis_frequency);

unique_freqs = sort(unique([input_data.center_frequency]));
unique_chans = sort(unique([input_data.channel_index]));

%filtered_data = input_data([input_data.channel_index] == unique_chans(21));
%filtered_data = input_data([input_data.center_frequency] == unique_freqs(14));

filtered_data = input_data([[input_data.channel_index] == unique_chans(21)] & [[input_data.lo_index] == 0]);

selected_data = filtered_data(1);

t = [0:4095]' * 1/selected_data.fs;

figure(1);
subplot(5, 1, 1);
plot(t, [selected_data.iq_data_I], t, [selected_data.iq_data_Q]);
subplot(5, 1, 2);
plot([selected_data.iq_amplitude]);
subplot(5, 1, 3);
plot([selected_data.fft_power_dB]);
subplot(5, 1, 4);
plot([selected_data.features.iq_acorr_abs]);
subplot(5, 1, 5);
plot([selected_data.features.frequency_acorr_abs]);

amp_s = sort(selected_data.iq_amplitude);
amp_y = linspace(0, 1, length(amp_s));
amp_25th = amp_s(find(amp_y > 0.25, 1, "first"));
amp_75th = amp_s(find(amp_y > 0.75, 1, "first"));
amp_95th = amp_s(find(amp_y > 0.95, 1, "first"));
amp_95th / median(amp_s)
(amp_75th - amp_25th) / median(amp_s)

figure(2);
subplot(4,1,1);
plot(selected_data.features.amplitude_hist_edges(1:128), selected_data.features.amplitude_hist_count);
subplot(4,1,2);
plot(amp_s, amp_y);

subplot(4,1,3);
plot(selected_data.features.frequency_hist_edges(1:128), selected_data.features.frequency_hist_count);

subplot(4,1,4);
%plot(selected_data.features.frequency_data);
g = kaiser(64,5);
ol = 48;
nfft = 128;
spectrogram(selected_data.iq_data,g,ol,nfft,40e3);

figure(3);
subplot(4,1,1);
instfrq = selected_data.fs/(2*pi) * diff(unwrap(angle(selected_data.iq_data)));

t_sel = (t < 80e-3);

%plot(t(1:end-1), instfrq);
plot(t(t_sel), instfrq(t_sel));

instfrq_m = instfrq - mean(instfrq);

subplot(4,1,2);
plot(t(t_sel), instfrq_m(t_sel).^2);

xc = fftshift(xcorr(instfrq(t_sel)));
subplot(4,1,3);
plot(abs(xc));

subplot(4,1,4);


figure(4);
subplot(4,1,1);
histogram(instfrq_m, 1024);


%%
combined_iq_I = [];
combined_iq_Q = [];

for ii = 1:length(filtered_data)
    combined_iq_I = [combined_iq_I; filtered_data(ii).iq_data_I];
    combined_iq_Q = [combined_iq_Q; filtered_data(ii).iq_data_Q];
end

% for ii = 1:length(input_data)
%     combined_iq_I = [combined_iq_I; input_data(ii).iq_data_I];
%     combined_iq_Q = [combined_iq_Q; input_data(ii).iq_data_Q];
% end

combined_iq = combined_iq_I + 1j * combined_iq_Q;

combined_t = [0:length(combined_iq_I)-1]' * 1/selected_data.fs;
combined_instfrq = selected_data.fs/(2*pi) * diff(unwrap(angle(combined_iq)));

figure(5);
subplot(4,1,1);
plot(combined_t, combined_iq_I, combined_t, combined_iq_Q);

subplot(4,1,2);
plot(combined_t(1:end-1), combined_instfrq);

subplot(4,1,3);
xc = fftshift(xcorr(combined_instfrq));
plot(abs(xc));

subplot(4,1,4);
plot([filtered_data.lo_frequency]);

figure(6);

g = kaiser(256,5);
ol = 220;
nfft = 512;

spectrogram(combined_iq,g,ol,nfft,40e3);




%%
%marker_t = 0:4096:length(combined_t);

total_power = sum([selected_data.fft_power]);
power_cs = cumsum([selected_data.fft_power]) / total_power;
power_ci = find(power_cs >= 0.5, 1);

power_95 = find(power_cs >= 0.95, 1);
power_05 = find(power_cs < 0.05, 1, "last");

bandwidth = (power_95 - power_05) * (1/length(power_cs)) * 40e3

figure(7);
subplot(3,1,1);
plot([selected_data.fft_power]);
subplot(3,1,2);
plot([0:length(power_cs)-1], power_cs, [power_ci, power_ci], [0, 1], [power_05, power_05], [0, 1], [power_95, power_95], [0, 1]);