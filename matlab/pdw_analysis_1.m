reload = 0;

if reload
    filename = 'recorded_data-20241120-225322.log';
    lines = readlines(filename);
    pdw_reports = [];
    init_done = false;
    
    for ii = 1:length(lines)
        if strlength(lines(ii)) <= 1
            continue
        end
    
        decoded_line = jsondecode(lines(ii));
        data = decoded_line.data;
        if ~isfield(data, 'pdw_pulse_report')
            continue;
        end    
        
        report = data.pdw_pulse_report;
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
    end

end

valid_reports = pdw_reports([pdw_reports.buffered_frame_valid] & ([pdw_reports.pulse_duration] > 50) & ([pdw_reports.recorded_pulse_snr] > 10));

for ii = 1:16:length(valid_reports)
     figure(1);
     for jj = 1:16
         ax = subplot(4,4,jj);
         pdw_index = ii + (jj - 1);
         report = valid_reports(pdw_index);
         iq_stop = min(8 + report.pulse_duration + 8, 50);

         plot(ax, 1:iq_stop, real(report.recorded_iq_data(1:iq_stop)), 1:iq_stop, imag(report.recorded_iq_data(1:iq_stop)), 1:iq_stop, sqrt(report.recorded_power(1:iq_stop)), [1, iq_stop], sqrt([report.pulse_threshold, report.pulse_threshold]));
     end
     pause();
end
