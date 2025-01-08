data_path = 'C:/drone_data/Radio-Frequency Control and Video Signal Recordings of Drones';

% The drones were recorded at 2.44 GHz and 5.8 GHz center frequencies (with the exception of Yuneec Typhoon H at 5.7 GHz) if the drone supported both.
% In the dataset, these center frequencies were denoted with 2G and 5G in the filename, respectively.
%The sampling frequency was 120 MHz at 2.44 GHz and 200 MHz at 5.8 GHz.

drone_entries = {{'DJI_inspire_2_2G.bin',               2.440e9, 120e6};
                 {'DJI_inspire_2_5G_1of2.bin',          5.800e9, 200e6};
                 {'DJI_inspire_2_5G_2of2.bin',          5.800e9, 200e6};
                 {'DJI_matrice_100_2G.bin',             2.440e9, 120e6};
                 {'DJI_matrice_210_2G.bin',             2.440e9, 120e6};
                 {'DJI_matrice_210_5G_2of2.bin',        5.800e9, 200e6};
                 {'DJI_mavic_mini_2G.bin',              2.440e9, 120e6};
                 {'DJI_mavic_pro_2G.bin',               2.440e9, 120e6};
                 {'DJI_phantom_4_2G.bin',               2.440e9, 120e6};
                 {'DJI_phantom_4_pro_plus_2G.bin',      2.440e9, 120e6};
                 {'DJI_phantom_4_pro_plus_5G_1of2.bin', 5.800e9, 200e6};
                 {'DJI_phantom_4_pro_plus_5G_2of2.bin', 5.800e9, 200e6};
                 {'Parrot_disco_2G.bin',                2.440e9, 120e6};
                 {'Parrot_mambo_control_2G.bin',        2.440e9, 120e6};
                 {'Parrot_mambo_video_2G.bin',          2.440e9, 120e6};
                 {'Yuneec_typhoon_h_2G_1of2.bin',       2.440e9, 120e6};
                 {'Yuneec_typhoon_h_2G_2of2.bin',       2.440e9, 120e6};
                 {'Yuneec_typhoon_h_5G.bin',            5.700e9, 200e6};
                };



filepath = 'DJI_inspire_2_2G.bin';
input_fs = 120e6;  % Use 120e6 for 2.4 GHz and 200e6 for 5.8 GHz

for ii = 1:length(drone_entries)
    filename = drone_entries{ii}{1};
    input_f0 = drone_entries{ii}{2};
    input_fs = drone_entries{ii}{3};

    filepath = sprintf('%s/%s', data_path, filename);

    iq_data = get_drone_data(filepath);
    run_model(iq_data, input_f0, input_fs, filename);
    break;
end

function iq_data = get_drone_data(filepath)
    iq_data = drone_data_tu_load_bin(filepath);
    iq_data = (iq_data-mean(iq_data))/(sqrt(var(iq_data)));
end

function run_model(iq_data, input_f0, input_fs, filepath)
    plot_dir = './plot';

    dwell_freqs = [96.0:48.0:6000.0].' * 1e6;
    channel_spacing = 3.84e6;
    chan_mask = 0x7FFE;
    num_channels = 16;
    output_fs = 61.44e6;
       
    input_freq_range = [input_f0 - input_fs/2, input_f0 + input_fs/2];
    
    valid_dwells = [];
    valid_channels = zeros(0, 'logical');
    
    for ii = 1:length(dwell_freqs)
        channel_freqs = dwell_freqs(ii) + channel_spacing * [-num_channels/2:(num_channels/2 - 1)].';
        channel_valid = zeros(length(channel_freqs), 1, 'logical');
        dwell_found = 0;
        for jj = 1:length(channel_freqs)
            channel_freq = channel_freqs(jj);
            if (channel_freq >= input_freq_range(1)) && (channel_freq <= input_freq_range(2)) && bitget(chan_mask, jj)
                dwell_found = 1;
                channel_valid(jj) = true;
            end
        end
        
        if dwell_found
            valid_dwells = [valid_dwells; dwell_freqs(ii)];
            valid_channels = [valid_channels, channel_valid];
            continue;
        end
    end
    
    dwell_freq_shift = input_f0 - valid_dwells;
    
    len_step = gcd(input_fs, output_fs);

    N = min(2e7, floor(length(iq_data)/len_step)*len_step); %4e7;
    selected_iq     = iq_data(1:N);
    selected_t      = (1:length(selected_iq)).' * (1/input_fs);
    resampled_iq    = zeros(length(selected_iq) * output_fs/input_fs, length(dwell_freq_shift));
    
    for ii = 1:length(dwell_freq_shift)
        w_0                 = 2*pi*-dwell_freq_shift(ii);
        shifted_iq          = selected_iq .* exp(-1j*w_0*selected_t);
        resampled_iq(:, ii) = resample(shifted_iq, output_fs, input_fs);
    end
    
    f = figure(1);
    subplot(2,1,1);
    spectrogram(selected_iq,blackman(512),[],[],input_fs,'centered');
    title(filepath, 'Interpreter', 'none');
    
    for ii = 1:length(dwell_freq_shift)
        subplot(2, length(dwell_freq_shift), length(dwell_freq_shift) + ii);
        spectrogram(resampled_iq(:, ii), blackman(512), [], [], output_fs, 'centered');
    end
    
    set(f, 'Position',  [100, 100, 800, 600]);

    s = split(filepath, '.');
    file_base = s{1};

    fig_fn = sprintf('%s/%s_input_%d.png', plot_dir, file_base, num_channels);
    saveas(f, fig_fn);    

    clear selected_iq
    clear selected_t
    clear shifted_iq
    
    threshold_fac = 2;
    
    f = figure(2);
    for ii = 1:length(dwell_freq_shift)
        [chan_data, chan_fs] = channelizer_64_model(resampled_iq(:, ii), output_fs);
        chan_data = chan_data(:, valid_channels(:, ii).');
        chan_power = abs(chan_data);
        
        chan_threshold = mean(chan_power, 1) * threshold_fac;
        chan_det = zeros(size(chan_power), 'logical');
        for jj = 1:size(chan_det, 2)
            chan_det(:, jj) = chan_power(:, jj) > chan_threshold(jj);
        end
    
        subplot(2, length(dwell_freq_shift), ii);
        imagesc(chan_power);
        subplot(2, length(dwell_freq_shift), length(dwell_freq_shift) + ii);
        imagesc(chan_det);
    end
    
    %title(filepath, 'Interpreter', 'none');
    set(f, 'Position',  [100, 100, 800, 600]);
    fig_fn = sprintf('%s/%s_output.png', plot_dir, file_base);
    saveas(f, fig_fn);    
end