reload = 1;

fast_clock_period = 1/(4*61.44e6);
channel_clock_period = (32/61.44e6);

if reload
    filename = 'analysis-20241123-132126.log';
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

pdw_freqs = unique([pdw_reports.channel_frequency]');


%freq = 1224.0;
%freq = 1323.84; %pdw_freqs(5)

% freq_1 = 1252.8;
% freq_2 = 1253.76;
% matching_pdws_1 = pdw_reports([pdw_reports.channel_frequency] == freq_1);
% matching_pdws_2 = pdw_reports([pdw_reports.channel_frequency] == freq_2);
% figure(1);
% subplot(2,1,1);
% plot([matching_pdws_1.pulse_start_time], [matching_pdws_1.pulse_power], 'o', [matching_pdws_2.pulse_start_time], [matching_pdws_2.pulse_power], 'x');
% subplot(2,1,2);
% plot([matching_pdws_1.pulse_start_time], [matching_pdws_1.pulse_duration], 'o', [matching_pdws_2.pulse_start_time], [matching_pdws_2.pulse_duration], 'x');
% 

freq = 1336.32;
%freq = 2711.04;
%freq = 2880;
matching_pdws = pdw_reports([pdw_reports.channel_frequency] == freq);

td = get_pri_hist_full([matching_pdws.pulse_start_time], [matching_pdws.dwell_seq_num]);

max_pri = 14000e-6 * 4;
ts = 1/1.92e6;
max_pri_clks = max_pri / ts;
adjusted_max_pri_clks = 2^ceil(log2(max_pri_clks));
max_hist_length = 4096;
if adjusted_max_pri_clks > max_hist_length
    pri_bin_width = adjusted_max_pri_clks / max_hist_length; 
    hist_length = max_hist_length;
else
    pri_bin_width = 1;
    hist_length = adjusted_max_pri_clks;
end
pri_bin_ranges = 0:pri_bin_width:(adjusted_max_pri_clks - pri_bin_width);
pri_bin_centers = pri_bin_ranges + pri_bin_width/2;

td_m = td(:, 1:1) / 32;
td_m = td_m(td_m ~= 0);
%pri_bin_counts = histc(td_m, pri_bin_ranges);

tdd = get_toa_diff_by_dwell([matching_pdws.pulse_start_time], [matching_pdws.dwell_seq_num])
dwell_seqs = unique(tdd(:, 1));

figure(1);
for ii = 1:16
    dwell_td = tdd(tdd(:, 1) == dwell_seqs(ii), 2);
    dwell_td = dwell_td(1:end-1);
    dwell_bc = histc(dwell_td, pri_bin_ranges);

    subplot(16, 1, ii);
    bar(pri_bin_ranges * ts, dwell_bc, 'histc');

    dwell_bc_norm = dwell_bc ./ sum(dwell_bc);
    fprintf('dwell[%d]: std=%f\n', ii, std(dwell_bc_norm));
end



return
figure(1); bar(pri_bin_ranges * ts, pri_bin_counts, 'histc');
figure(2); plot(td_m * ts, 'o');
return

function td_by_dwell = get_toa_diff_by_dwell(toa, dwell_seq)
    td_by_dwell = zeros([length(toa), 2]);
    td_by_dwell(:, 1) = dwell_seq;
    for ii = 1:(length(toa) - 1)
        if dwell_seq(ii) == dwell_seq(ii + 1)
            td_by_dwell(ii, 2) = toa(ii + 1) - toa(ii);
        end
    end
    %td_by_dwell(:, 2) = (td_by_dwell(:, 2) / 32) * (1/1.92e6);
    td_by_dwell(:, 2) = (td_by_dwell(:, 2) / 32);
end

function td = get_pri_hist_full(toa, dwell_seq)
    N_diffs = 2;
    dwell_seqs = unique(dwell_seq);

    td = zeros([length(toa) - 1, N_diffs]);

    for i_dwell = 1:length(dwell_seqs)
        dwell_mask = dwell_seq == dwell_seqs(i_dwell);
        dwell_pulses = toa(dwell_mask);
        td_dwell = get_toa_diff_single_dwell(dwell_pulses, N_diffs);
        td(dwell_mask, :) = td_dwell;
    end
end

function td = get_toa_diff_single_dwell(toa, N_diffs)
    td = zeros([length(toa), N_diffs]);

    for i_diff = 1:N_diffs
        for ii = 1:(length(toa) - i_diff)
            td(ii, i_diff) = toa(ii + i_diff) - toa(ii);
        end
    end
end

