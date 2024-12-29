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
    self.logger   = logger
    self.recorder = pluto_esm_data_recorder.pluto_esm_data_recorder(log_dir, "analysis", config["analysis_config"]["enable_pdw_recording"])
    self.config   = config

    self.pdw_processor        = pluto_esm_pdw_processor.pluto_esm_pdw_processor(logger)
    self.dwell_processor      = pluto_esm_dwell_processor.pluto_esm_dwell_processor(logger, config)
    self.pulsed_tracker       = pluto_esm_pulsed_emitter_tracker.pluto_esm_pulsed_emitter_tracker(logger, self.pdw_processor, config)
    self.modulation_analyzer  = pluto_esm_pdw_modulation_analysis.pluto_esm_pdw_modulation_analysis(config["analysis_config"]["modulation_analysis"])

    self.confirmed_pulsed_signals_to_render     = []
    self.confirmed_cw_primary_signals_to_render = []

    self.pending_dwell_reports        = []
    self.pending_pdw_summary_reports  = []
    self.pending_pdw_pulse_reports    = []
    self.pending_combined_data        = []

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

      self.recorder.log(pdw)

    self.recorder.flush()

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
      assert (expected_pulse_count == actual_pulse_count)
      self.logger.log(self.logger.LL_INFO, "[analysis_processor] _process_matched_reports: seq_num={} freq={} num_pulses={}".format(combined_data["pdw_summary_report"]["dwell_seq_num"],
                                                                                                                                    combined_data["dwell_report"]["dwell_data"].frequency,
                                                                                                                                    actual_pulse_count))
      self._merge_pdws(combined_data)
      self._populate_dwell_channels(combined_data)
      self.pdw_processor.submit_dwell_data(combined_data)
      self.dwell_processor.submit_dwell_data(combined_data)

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

  def _update_tracked_emitters(self):
    now = time.time()
    if (now - self.last_emitter_update_time) < self.emitter_update_interval:
      return
    self.last_emitter_update_time = now

    self.confirmed_pulsed_signals_to_render       = copy.deepcopy(self.pulsed_tracker.confirmed_emitters)
    self.confirmed_cw_primary_signals_to_render   = copy.deepcopy(self.dwell_processor.combined_data_primary)
    self.confirmed_cw_secondary_signals_to_render = copy.deepcopy(self.dwell_processor.combined_data_secondary)

  def submit_report(self, report):
    if "pdw_pulse_report" in report:
      self.pending_pdw_pulse_reports.append(report)
    elif "pdw_summary_report" in report:
      self.pending_pdw_summary_reports.append(report)
    elif "dwell_report" in report:
      self.pending_dwell_reports.append(report)
    else:
      raise RuntimeError("invalid report")

  def update(self):
    self.dwell_processor.update()
    self.pdw_processor.update()
    self.pulsed_tracker.update()
    self._match_dwell_reports()
    self._process_matched_reports()
    self._update_tracked_emitters()

  def shutdown(self, reason):
    self.recorder.shutdown(reason)
