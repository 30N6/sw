import pluto_esm_logger
import pluto_esm_data_recorder
from pluto_esm_hw_pkg import *
import time
import numpy as np

class pluto_esm_analysis_processor:
  def __init__(self, logger, log_dir, config):
    self.logger   = logger
    self.recorder = pluto_esm_data_recorder.pluto_esm_data_recorder(log_dir, "analysis", config["analysis_config"]["enable_pdw_recording"])
    self.config   = config

    self.pdw_processor = pluto_esm_pdw_processor(logger)

    self.pending_dwell_reports        = []
    self.pending_pdw_summary_reports  = []
    self.pending_pdw_pulse_reports    = []
    self.pending_combined_data        = []
    #self.merged_pdws                  = []

    self.center_channel_index = (ESM_NUM_CHANNELS_NARROW // 2)
    self.channel_spacing      = (ADC_CLOCK_FREQUENCY / ESM_NUM_CHANNELS_NARROW) / 1e6

  def _merge_pdws(self, combined_data):
    dwell_report = combined_data["dwell_report"]["dwell_report"]
    dwell_freq = combined_data["dwell_report"]["dwell_data"].frequency

    for pdw in combined_data["pdw_pulse_reports"]:
      pulse_channel = pdw["pulse_channel"]
      pdw["channel_frequency"]      = dwell_freq + (pulse_channel - self.center_channel_index) * self.channel_spacing
      pdw["dwell_channel_entry"]    = dwell_report["channel_data"][pulse_channel]
      pdw["dwell_num_samples"]      = dwell_report["num_samples"]
      pdw["dwell_threshold_shift"]  = dwell_report["threshold_shift_narrow"]

      #self.merged_pdws.append(pdw)
      self.recorder.log(pdw)

    self.pdw_processor.submit_pdws_for_dwell(combined_data["pdw_pulse_reports"])
    self.recorder.flush()

  def _process_matched_reports(self):
    while len(self.pending_combined_data) > 0:
      combined_data         = self.pending_combined_data.pop(0)
      expected_pulse_count  = combined_data["pdw_summary_report"]["dwell_pulse_total_count"] - combined_data["pdw_summary_report"]["dwell_pulse_drop_count"]
      actual_pulse_count    = len(combined_data["pdw_pulse_reports"])
      assert (expected_pulse_count == actual_pulse_count)
      self.logger.log(self.logger.LL_INFO, "[analysis_processor] _process_matched_reports: seq_num={} freq={} num_pulses={}".format(combined_data["pdw_summary_report"]["dwell_seq_num"],
                                                                                                                                    combined_data["dwell_report"]["dwell_data"].frequency,
                                                                                                                                    actual_pulse_count))
      if actual_pulse_count > 0:
        self._merge_pdws(combined_data)

  def _match_dwell_reports(self):
    if (len(self.pending_dwell_reports) == 0) or (len(self.pending_pdw_summary_reports) == 0):
      return

    pdw_seq_num   = self.pending_pdw_summary_reports[0]["pdw_summary_report"]["dwell_seq_num"]
    dwell_seq_num = self.pending_dwell_reports[0]["dwell_report"]["dwell_seq_num"]

    if pdw_seq_num != dwell_seq_num:
      assert (pdw_seq_num > dwell_seq_num)
      self.logger.log(self.logger.LL_WARN, "[analysis_processor] _match_dwell_reports: missed PDW dwell detected! dwell_seq_num={} pdw_seq_num={}".format(dwell_seq_num, pdw_seq_num))
      self.pending_dwell_reports.pop(0)
      return

    matched_pulse_reports = []
    while len(self.pending_pdw_pulse_reports) > 0:
      pdw_dwell_seq_num = self.pending_pdw_pulse_reports[0]["pdw_pulse_report"]["dwell_seq_num"]
      if pdw_dwell_seq_num == dwell_seq_num:
        matched_pulse_reports.append(self.pending_pdw_pulse_reports.pop(0)["pdw_pulse_report"])
      else:
        assert(pdw_dwell_seq_num > dwell_seq_num)
        break

    self.pending_combined_data.append({"dwell_report": self.pending_dwell_reports.pop(0),
                                       "pdw_summary_report": self.pending_pdw_summary_reports.pop(0)["pdw_summary_report"],
                                       "pdw_pulse_reports": matched_pulse_reports})

  def submit_report(self, report):
    if "pdw_pulse_report" in report:
      self.pending_pdw_pulse_reports.append(report)
    elif "pdw_summary_report" in report:
      self.pending_pdw_summary_reports.append(report)
    elif "dwell_report" in report:
      self.pending_dwell_reports.append(report)

  def update(self):
    self.pdw_processor.update()
    self._match_dwell_reports()
    self._process_matched_reports()

  def shutdown(self, reason):
    self.recorder.shutdown(reason)


class pluto_esm_pdw_processor:
  def __init__(self, logger):
    self.logger = logger

    self.pdw_history = []
    self.max_pdw_age = 60 #TODO: config?

    self.hist_pd  = multi_level_histogram([0, 16383], [1, 4, 16, 64])
    self.hist_pri = multi_level_histogram([0, 65535], [1, 8, 64, 256])

  def submit_pdws_for_dwell(self, pdws):
    now = time.time()

    dwell_freqs = np.unique([p["channel_frequency"] for p in pdws])
    for channel_freq in dwell_freqs:
      channel_pdws    = [p for p in pdws if (p["channel_frequency"] == channel_freq)]
      pulse_duration  = np.asarray([p["pulse_duration"] for p in channel_pdws])
      pulse_toa       = np.asarray([p["pulse_start_time"] for p in channel_pdws])
      pulse_pri       = np.diff(pulse_toa)
      pulse_power     = np.asarray([p["pulse_power_accum"] for p in channel_pdws]) / pulse_duration

      self.pdw_history.append({"time": now,
                               "pdws": channel_pdws,
                               "channel_freq": channel_freq,
                               "pulse_duration": pulse_duration,
                               "pulse_pri": pulse_pri,
                               "pulse_power": pulse_power})
      self.hist_pd.add_dwell_pdws(channel_freq, pulse_duration)
      self.hist_pri.add_dwell_pdws(channel_freq, pulse_pri)

  def update(self):
    now = time.time()

    while len(self.pdw_history) > 0:
      if (now - self.pdw_history[0]["time"]) > self.max_pdw_age:
        removed_pdws = self.pdw_history.pop(0)
        self.hist_pd.remove_dwell_pdws(removed_pdws["channel_freq"], removed_pdws["pulse_duration"])
        self.hist_pri.remove_dwell_pdws(removed_pdws["channel_freq"], removed_pdws["pulse_pri"])
      else:
        break

class multi_level_histogram:
  def __init__(self, hist_range, bin_sizes):
    self.hist_range = hist_range
    self.bin_sizes = bin_sizes

    self.hist_data_by_bin_size = {}
    self.bin_count_by_bin_size = {}
    for bin_size in bin_sizes:
      self.hist_data_by_bin_size[bin_size] = {}
      self.bin_count_by_bin_size[bin_size] = (hist_range[1] - hist_range[0] + 1) // bin_size

  def add_dwell_pdws(self, freq, data):
    for bin_size in self.bin_sizes:
      bin_count = self.bin_count_by_bin_size[bin_size]

      if freq not in self.hist_data_by_bin_size[bin_size]:
        self.hist_data_by_bin_size[bin_size][freq] = np.zeros(bin_count, dtype=np.uint32)

      data_index = data // bin_size
      data_index[data_index >= bin_count] = bin_count - 1
      self.hist_data_by_bin_size[bin_size][freq][data_index] += 1

  def remove_dwell_pdws(self, freq, data):
    for bin_size in self.bin_sizes:
      bin_count = self.bin_count_by_bin_size[bin_size]

      data_index = data // bin_size
      data_index[data_index >= bin_count] = bin_count - 1
      self.hist_data_by_bin_size[bin_size][freq][data_index] -= 1
