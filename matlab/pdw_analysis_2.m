reload = 0;

fast_clock_period = 1/(4*61.44e6);
channel_clock_period = (32/61.44e6);

if reload
    filename = 'analysis-20241123-140158.log';
    lines = readlines(filename);
    pdw_reports = [];
    init_done = false;
    
    for ii = 1:length(lines)
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

pdw_freqs                   = unique([pdw_reports.channel_frequency]');
pdw_count_by_freq           = zeros([length(pdw_freqs), 1]);
pdw_energy_by_freq          = zeros([length(pdw_freqs), 1]);
pdw_mean_imp_snr_by_freq    = zeros([length(pdw_freqs), 1]);
pdw_mean_rec_snr_by_freq    = zeros([length(pdw_freqs), 1]);

for ii = 1:length(pdw_freqs)
    pdw_match = [pdw_reports.channel_frequency] == pdw_freqs(ii);
    matching_pdws = pdw_reports(pdw_match);

    pdw_count_by_freq(ii)           = sum(pdw_match);
    pdw_energy_by_freq(ii)          = sum([matching_pdws.pulse_power_accum]);
    pdw_mean_imp_snr_by_freq(ii)    = mean([matching_pdws.implied_pulse_snr]);
    pdw_mean_rec_snr_by_freq(ii)    = mean([matching_pdws.recorded_pulse_snr]);
end

for ii = 1:length(pdw_reports)
    report = pdw_reports(ii);
end

figure(1);
ax1 = subplot(3,1,1); 
plot(ax1, pdw_freqs, pdw_count_by_freq, 'o');
grid(ax1, 'on');
ax2 = subplot(3,1,2); grid('on');
plot(ax2, pdw_freqs, pdw_energy_by_freq, 'o');
grid(ax2, 'on');
ax3 = subplot(3,1,3); grid('on');
plot(ax3, pdw_freqs, pdw_mean_imp_snr_by_freq, 'o', pdw_freqs, pdw_mean_rec_snr_by_freq, 'x');
grid(ax3, 'on');

linkaxes([ax1, ax2, ax3], 'x');

figure(2);
plot([pdw_reports.pulse_power]);


%freq = 1224.0;
%freq = 1323.84; %pdw_freqs(5)
%freq = 1336.32; %pdw_freqs(6)

%freq = 1252.8;
%freq = 1253.76;

%freq = 1212.48;
%freq = 2700.48;
%freq = 2880.0;

%freq = pdw_freqs(176); %freq = 2929.92;
freq = 2914.56;
%freq = 2960.64;

matching_pdws = pdw_reports(([pdw_reports.channel_frequency] == freq) & ([pdw_reports.pulse_duration] > 1));

%pulse_gap = zeros([length(matching_pdws), 1]);
%for ii = 2:length(matching_pdws)
%    pulse_gap(ii) = matching_pdws(ii).ts_pulse_start - matching_pdws(ii - 1).ts_pulse_end;
%end
%pulse_gap(pulse_gap > 50e-3) = 0;

%min_gap = 4e-6;
%matching_pdws = matching_pdws(pulse_gap > min_gap);
%pulse_gap = pulse_gap(pulse_gap > min_gap);

valid_sample_count = [matching_pdws.buffered_frame_valid] .* min(50, max([matching_pdws.pulse_duration] + 8, 16));
sample_offset = [0, cumsum(valid_sample_count)];
combined_iq_data    = zeros([sum(valid_sample_count), 1]);
combined_power_data = zeros([sum(valid_sample_count), 1]);
for ii = 1:length(matching_pdws)
    if ~matching_pdws(ii).buffered_frame_valid
        continue;
    end

    sample_start = sample_offset(ii) + 1;
    sample_end = sample_start + valid_sample_count(ii) - 1;
    combined_iq_data(sample_start:sample_end) = matching_pdws(ii).recorded_iq_data(1:valid_sample_count(ii));
    combined_power_data(sample_start:sample_end) = matching_pdws(ii).recorded_power(1:valid_sample_count(ii));
end

filtered_pri = diff([matching_pdws.pulse_start_time] * fast_clock_period);
filtered_pri(filtered_pri > 50e-3) = nan;

num_plots = 6;
figure(3);
ax1 = subplot(num_plots, 1, 1);
plot(ax1, [matching_pdws.pulse_duration]);

ax2 = subplot(num_plots, 1, 2);
plot(ax2, 1:length(matching_pdws), [matching_pdws.pulse_power], 1:length(matching_pdws), [matching_pdws.recorded_pulse_power]);

ax3 = subplot(num_plots, 1, 3);
plot(ax3, [matching_pdws.pulse_threshold]);

if length(matching_pdws) < 5000
    ax4 = subplot(num_plots, 1, 4);
    plot(ax4, 1:length(combined_iq_data), real(combined_iq_data), 1:length(combined_iq_data), imag(combined_iq_data), 1:length(combined_power_data), sqrt(combined_power_data));
end

ax5 = subplot(num_plots, 1, 5);
plot(ax5, filtered_pri, 'o');

%ax6 = subplot(num_plots, 1, 6);
%plot(ax6, pulse_gap, 'o');

% valid_reports = pdw_reports([pdw_reports.buffered_frame_valid] & ([pdw_reports.pulse_duration] > 50) & ([pdw_reports.recorded_pulse_snr] > 10));
% for ii = 1:16:length(valid_reports)
%      figure(1);
%      for jj = 1:16
%          ax = subplot(4,4,jj);
%          pdw_index = ii + (jj - 1);
%          report = valid_reports(pdw_index);
%          iq_stop = min(8 + report.pulse_duration + 8, 50);
% 
%          plot(ax, 1:iq_stop, real(report.recorded_iq_data(1:iq_stop)), 1:iq_stop, imag(report.recorded_iq_data(1:iq_stop)), 1:iq_stop, sqrt(report.recorded_power(1:iq_stop)), [1, iq_stop], sqrt([report.pulse_threshold, report.pulse_threshold]));
%      end
%      pause();
% end
