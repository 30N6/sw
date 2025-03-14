reload = 0;

fast_clock_period = 1/(4*61.44e6);
channel_clock_period = (32/61.44e6);

if reload
    filename = 'analysis-20241123-132126.log';
    lines = readlines(filename);
    pdw_reports = [];
    init_done = false;
    
    %num_lines = min(length(lines), 10000);
    num_lines = length(lines);

    for ii = 1:num_lines
        if strlength(lines(ii)) <= 1
            continue
        end
    
        decoded_line = jsondecode(lines(ii));
        report = decoded_line.data;
        if ~isfield(report, 'pulse_seq_num')
            continue;
        end    
        
        if ~report.buffered_frame_valid
            report.buffered_frame_data = zeros([50, 2]);
        end

        if ~init_done
            pdw_reports = report
            init_done = true;
        else
            pdw_reports(end + 1) = report;
        end
    end

    clear lines;
    pdw_reports = pdw_reports';

    for ii = 1:length(pdw_reports)
        pdw_reports(ii).recorded_iq_data        = pdw_reports(ii).buffered_frame_data(:, 1) + pdw_reports(ii).buffered_frame_data(:, 2) * 1j;
        pdw_reports(ii).recorded_power          = abs(pdw_reports(ii).recorded_iq_data) .^ 2;
        pdw_reports(ii).recorded_noise_power    = mean(pdw_reports(ii).recorded_power(1:8));
    
        iq_length = min(50 - 8, pdw_reports(ii).pulse_duration);
        pdw_reports(ii).recorded_pulse_power    = mean(pdw_reports(ii).recorded_power(9:(9 + iq_length - 1)));
        pdw_reports(ii).recorded_pulse_snr      = pdw_reports(ii).recorded_pulse_power / max(pdw_reports(ii).recorded_noise_power, 1);
        pdw_reports(ii).pulse_power             = pdw_reports(ii).pulse_power_accum / pdw_reports(ii).pulse_duration;
        pdw_reports(ii).implied_pulse_snr       = pdw_reports(ii).pulse_power / pdw_reports(ii).pulse_threshold;

        pdw_reports(ii).ts_pulse_start = pdw_reports(ii).pulse_start_time * fast_clock_period;
        pdw_reports(ii).ts_pulse_end   = pdw_reports(ii).ts_pulse_start + pdw_reports(ii).pulse_duration * channel_clock_period;
    end

end

pdw_freqs = unique([pdw_reports.channel_frequency]');

%freq = 1336.32;    %LFM
%freq = 1213.44;
%freq = 1218.24;
%freq = 1253.76;
freq = 1213.44;

matching_pdws = pdw_reports(([pdw_reports.channel_frequency] == freq) & ([pdw_reports.buffered_frame_valid] == 1));

dt = channel_clock_period;

figure(1);
num_subplots = 12;
for ii = 1:num_subplots
    pdw = matching_pdws(ii);

    subplot(num_subplots, 4, 4 * ii - 3);
    plot(1:length(pdw.recorded_iq_data), real(pdw.recorded_iq_data), 1:length(pdw.recorded_iq_data), imag(pdw.recorded_iq_data), 1:length(pdw.recorded_iq_data), abs(pdw.recorded_iq_data));
    
    phase = unwrap(atan2(imag(pdw.recorded_iq_data(9:end-2)), real(pdw.recorded_iq_data(9:end-2))));
    freq = (1/(2*pi)) * diff(phase) / dt;
    
    x_phase = (0:length(phase)-1) * dt;
    [p_p, S_phase] = polyfit(x_phase, phase, 2);
    ss_res = S_phase.normr ^ 2;
    ss_tot = sum((freq - mean(freq)).^2);
    r_squared_phase = 1 - ss_res/ss_tot;
    p_phase = p_p(1) * (x_phase.^2) + p_p(2) * x_phase + p_p(3);

    x_freq = (0:length(freq)-1).' * dt;
    [p_f, S_freq] = polyfit(x_freq, freq, 1);
    ss_res = S_freq.normr ^ 2;
    ss_tot = sum((freq - mean(freq)).^2);
    r_squared_freq = 1 - ss_res/ss_tot;
    p_freq = p_f(1) * x_freq + p_f(2);

    fprintf("[%d]: normr=%f %f  r_squared=%f %f  snr=%f snr=%f -- slope: %f %f \n", ii, S_phase.normr/ length(x_phase), S_freq.normr / length(x_freq), r_squared_phase, r_squared_freq, ...
        pdw.implied_pulse_snr, pdw.recorded_pulse_snr, 2*p_p(1) * (1/(2*pi)), p_f(1));
    

    subplot(num_subplots, 4, 4 * ii - 2);
    plot(x_phase, phase, x_phase, p_phase);

    subplot(num_subplots, 4, 4 * ii - 1);
    plot(x_freq, freq, 'o-', x_freq, p_freq);

    subplot(num_subplots, 4, 4 * ii);

    if r_squared_freq > 0.1
        continue;
    end

    x_freq_a = x_freq(freq < p_freq);
    y_freq_a = freq(freq < p_freq);
    x_freq_b = x_freq(freq >= p_freq);
    y_freq_b = freq(freq >= p_freq);

    [p_fa, S_fa] = polyfit(x_freq_a, y_freq_a, 1);
    [p_fb, S_fb] = polyfit(x_freq_b, y_freq_b, 1);
    p_freq_a = p_fa(1) * x_freq_a + p_fa(2);
    p_freq_b = p_fb(1) * x_freq_b + p_fb(2);
        
    ss_res_a = S_fa.normr ^ 2;
    ss_tot_a = sum((y_freq_a - mean(y_freq_a)).^2);
    r_squared_freq_a = 1 - ss_res_a/ss_tot_a;
    
    ss_res_b = S_fa.normr ^ 2;
    ss_tot_b = sum((y_freq_b - mean(y_freq_b)).^2);
    r_squared_freq_b = 1 - ss_res_b/ss_tot_b;

    fprintf("  FSK: r_squared=%f %f\n", r_squared_freq_a, r_squared_freq_b);
        
    plot(x_freq_a, y_freq_a, 'o-', x_freq_b, y_freq_b, 'o-', x_freq_a, p_freq_a, x_freq_b, p_freq_b);
end