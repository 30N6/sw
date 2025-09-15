import pluto_esm_data_recorder
import pluto_esm_pdw_processor
import pluto_esm_dwell_processor
import pluto_esm_pulsed_emitter_tracker
import pluto_esm_pdw_modulation_analysis
from pluto_esm_hw_pkg import *
import time
import numpy as np
import copy

class pluto_esm_analysis_processor:
  def __init__(self, logger, log_dir, config):
    self.logger           = logger
    self.recorder_narrow  = pluto_esm_data_recorder.pluto_esm_data_recorder(log_dir, "analysis-narrow", config["analysis_config"]["enable_pdw_recording"])
    self.recorder_full    = pluto_esm_data_recorder.pluto_esm_data_recorder(log_dir, "analysis-full",   config["analysis_config"]["enable_pdw_recording"])
    self.config           = config

    self.pdw_processor        = pluto_esm_pdw_processor.pluto_esm_pdw_processor(logger, config)
    self.dwell_processor      = pluto_esm_dwell_processor.pluto_esm_dwell_processor(logger, config)
    self.pulsed_tracker       = pluto_esm_pulsed_emitter_tracker.pluto_esm_pulsed_emitter_tracker(logger, self.pdw_processor, config)
    self.modulation_analyzer  = pluto_esm_pdw_modulation_analysis.pluto_esm_pdw_modulation_analysis(config["analysis_config"]["modulation_analysis"])

    self.confirmed_pulsed_signals_to_render     = []
    self.confirmed_cw_primary_signals_to_render = []

    self.pending_dwell_reports_narrow           = []
    self.pending_pdw_summary_reports_narrow     = []
    self.pending_pdw_pulse_reports_narrow       = []
    self.pending_combined_data                  = []

    self.pending_pdw_pulse_reports_full         = []
    self.pending_pdw_summary_reports_full       = []

    self.dwell_frequency_by_seq_num             = {}

    self.center_channel_index = (ESM_NUM_CHANNELS_NARROW // 2)
    self.channel_spacing      = (ADC_CLOCK_FREQUENCY / ESM_NUM_CHANNELS_NARROW) / 1e6

    self.emitter_update_interval = 0.1
    self.last_emitter_update_time = 0

  def _merge_pdws(self, combined_data):
    dwell_report = combined_data["dwell_report"]["dwell_report"]
    dwell_freq = combined_data["dwell_report"]["dwell_data"].frequency

    for pdw in combined_data["pdw_pulse_reports"]:
      pulse_channel = pdw["pulse_channel"]
      pdw["channel_frequency"]      = dwell_freq + (pulse_channel - self.center_channel_index) * self.channel_spacing
      pdw["dwell_channel_entry"]    = dwell_report["channel_data"][pulse_channel]
      pdw["dwell_threshold_shift"]  = dwell_report["threshold_shift_narrow"]

      if pdw["buffered_frame_valid"]:
        mod_data = self.modulation_analyzer.check_intrapulse_modulation(pdw["pulse_duration"], pdw["buffered_frame_data"])
      else:
        mod_data = None
      pdw["modulation_data"] = mod_data

      self.recorder_narrow.log(pdw)

    self.recorder_narrow.flush()

  def _populate_dwell_channels(self, combined_data):
    dwell_freq          = combined_data["dwell_report"]["dwell_data"].frequency
    dwell_num_samples   = combined_data["dwell_report"]["dwell_report"]["num_samples"]
    dwell_channel_data  = combined_data["dwell_report"]["dwell_report"]["channel_data"]
    channel_mask        = combined_data["dwell_report"]["dwell_data"].hw_dwell_entry.channel_mask_narrow

    num_samples_by_channel_pdw = {}
    channel_data = {}

    for i in range(ESM_NUM_CHANNELS_NARROW):
      channel_freq = dwell_freq + (i - self.center_channel_index) * self.channel_spacing
      if (channel_mask & (1 << i)):
        num_samples_by_channel_pdw[channel_freq] = dwell_num_samples
      channel_data[channel_freq] = {"accum": dwell_channel_data[i]["accum"], "max": dwell_channel_data[i]["max"]}

    combined_data["dwell_num_samples_pdw"]  = num_samples_by_channel_pdw
    combined_data["dwell_channel_data"]     = channel_data

  def _process_matched_reports(self):
    while len(self.pending_combined_data) > 0:
      combined_data         = self.pending_combined_data.pop(0)
      expected_pulse_count  = combined_data["pdw_summary_report"]["dwell_pulse_total_count"] - combined_data["pdw_summary_report"]["dwell_pulse_drop_count"]
      actual_pulse_count    = len(combined_data["pdw_pulse_reports"])
      if (expected_pulse_count != actual_pulse_count):
        self.logger.log(self.logger.LL_WARN, "_process_matched_reports: WARNING -- pulse count mismatch: {} {}".format(expected_pulse_count, actual_pulse_count))
        self.logger.flush()

        print("_process_matched_reports: WARNING -- pulse count mismatch: {} {}".format(expected_pulse_count, actual_pulse_count))
        #print("combined_data: {}".format(combined_data))
      #assert (expected_pulse_count == actual_pulse_count)

      self.logger.log(self.logger.LL_INFO, "[analysis_processor] _process_matched_reports: seq_num={} freq={} num_pulses={}".format(combined_data["pdw_summary_report"]["dwell_seq_num"],
                                                                                                                                    combined_data["dwell_report"]["dwell_data"].frequency,
                                                                                                                                    actual_pulse_count))
      self._merge_pdws(combined_data)
      self._populate_dwell_channels(combined_data)
      self.pdw_processor.submit_dwell_data(combined_data)
      self.dwell_processor.submit_dwell_data(combined_data)

  def _match_dwell_reports(self):
    if (len(self.pending_dwell_reports_narrow) == 0) or (len(self.pending_pdw_summary_reports_narrow) == 0):
      return

    pdw_seq_num   = self.pending_pdw_summary_reports_narrow[0]["pdw_summary_report"]["dwell_seq_num"]
    dwell_seq_num = self.pending_dwell_reports_narrow[0]["dwell_report"]["dwell_seq_num"]

    if pdw_seq_num != dwell_seq_num:
      assert (pdw_seq_num > dwell_seq_num)
      self.logger.log(self.logger.LL_WARN, "[analysis_processor] _match_dwell_reports: missed PDW dwell detected! dwell_seq_num={} pdw_seq_num={}".format(dwell_seq_num, pdw_seq_num))
      self.pending_dwell_reports_narrow.pop(0)
      return

    matched_pulse_reports = []
    while len(self.pending_pdw_pulse_reports_narrow) > 0:
      pdw_dwell_seq_num = self.pending_pdw_pulse_reports_narrow[0]["pdw_pulse_report"]["dwell_seq_num"]
      if pdw_dwell_seq_num == dwell_seq_num:
        matched_pulse_reports.append(self.pending_pdw_pulse_reports_narrow.pop(0)["pdw_pulse_report"])
      else:
        if (pdw_dwell_seq_num <= dwell_seq_num):
          print("_match_dwell_reports: out of order seq num: pdw={} dwell={}".format(pdw_dwell_seq_num, dwell_seq_num))
        assert(pdw_dwell_seq_num > dwell_seq_num)
        break

    self.pending_combined_data.append({"dwell_report": self.pending_dwell_reports_narrow.pop(0),
                                       "pdw_summary_report": self.pending_pdw_summary_reports_narrow.pop(0)["pdw_summary_report"],
                                       "pdw_pulse_reports": matched_pulse_reports})

  def _update_tracked_emitters(self):
    now = time.time()
    if (now - self.last_emitter_update_time) < self.emitter_update_interval:
      return
    self.last_emitter_update_time = now

    self.confirmed_pulsed_signals_to_render       = copy.deepcopy(self.pulsed_tracker.confirmed_emitters)
    self.confirmed_cw_primary_signals_to_render   = copy.deepcopy(self.dwell_processor.combined_data_primary)
    self.confirmed_cw_secondary_signals_to_render = copy.deepcopy(self.dwell_processor.combined_data_secondary)

  def _process_full_path_reports(self):
    if len(self.pending_pdw_summary_reports_full) == 0:
      return

    dwell_seq_num = self.pending_pdw_summary_reports_full[0]["pdw_summary_report"]["dwell_seq_num"]

    if dwell_seq_num not in self.dwell_frequency_by_seq_num:
      return

    dwell_freq = self.dwell_frequency_by_seq_num[dwell_seq_num]

    while len(self.pending_pdw_pulse_reports_full) > 0:
      report = self.pending_pdw_pulse_reports_full[0]
      report_seq_num = report["pdw_pulse_report"]["dwell_seq_num"]
      assert (report_seq_num >= dwell_seq_num)

      if report_seq_num == dwell_seq_num:
        report["pdw_pulse_report"]["dwell_frequency"] = dwell_freq
        self.recorder_full.log(report)
        self.pending_pdw_pulse_reports_full.pop(0)
      elif report_seq_num > dwell_seq_num:
        break

    dwell_report = self.pending_pdw_summary_reports_full.pop(0)
    dwell_report["pdw_summary_report"]["dwell_frequency"] = dwell_freq
    self.recorder_full.log(dwell_report)

    self.dwell_frequency_by_seq_num.pop(dwell_seq_num)

  def submit_report(self, report):
    if "pdw_pulse_report" in report:
      if report["pdw_pulse_report"]["mod_id"] == ESM_MODULE_ID_PDW_NARROW:
        self.pending_pdw_pulse_reports_narrow.append(report)
      else:
        self.pending_pdw_pulse_reports_full.append(report)

    elif "pdw_summary_report" in report:
      if report["pdw_summary_report"]["mod_id"] == ESM_MODULE_ID_PDW_NARROW:
        self.pending_pdw_summary_reports_narrow.append(report)
      else:
        self.pending_pdw_summary_reports_full.append(report)

    elif "dwell_report" in report:
      self.pending_dwell_reports_narrow.append(report)
      self.dwell_frequency_by_seq_num[report["dwell_report"]["dwell_seq_num"]] = report["dwell_data"].frequency
    else:
      raise RuntimeError("invalid report")

  def update(self):
    self.recorder_full.flush()

    self.dwell_processor.update()
    self.pdw_processor.update()
    self.pulsed_tracker.update()

    self._match_dwell_reports()
    self._process_matched_reports()
    self._update_tracked_emitters()

    self._process_full_path_reports()

  def shutdown(self, reason):
    self.recorder_narrow.shutdown(reason)
    self.recorder_full.shutdown(reason)
