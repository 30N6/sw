import time
import numpy as np
import copy
import multiprocessing

from pluto_ecm_hw_pkg import *
import pluto_ecm_data_recorder
import pluto_ecm_modulation_analysis


class pluto_ecm_analysis_processor:
  def __init__(self, logger, log_dir, config, output_queue):
    self.logger       = logger
    self.recorder     = pluto_ecm_data_recorder.pluto_ecm_data_recorder(log_dir, "analysis", 1) #config["analysis_config"]["enable_pdw_recording"])
    self.config       = config
    self.output_queue = output_queue

    self.mod_analysis = pluto_ecm_modulation_analysis.pluto_ecm_modulation_analysis(config)

    self.center_channel_index = (ECM_NUM_CHANNELS // 2)
    self.channel_spacing      = (ADC_CLOCK_FREQUENCY / ECM_NUM_CHANNELS) / 1e6

    self.pending_scan_reports_iq    = []
    self.pending_scan_reports_bare  = []
    self.pending_tx_reports         = []

    self.scan_seq_num = 0
    self.scan_stats = {}
    self._clear_scan_stats()

    self.iq_stats_time    = time.time()
    self.iq_stats_count   = 0
    self.iq_stats_samples = 0

    self.process_pool = multiprocessing.Pool(4) #TODO: config
    self.pool_results = []

  def _clear_scan_stats(self):
    for entry in self.config["dwell_config"]["dwell_freqs"]:
      self.scan_stats[entry["freq"]] = {"iq_power_mean"         : [0  for i in range(ECM_NUM_CHANNELS)],
                                        "iq_power_median"       : [0  for i in range(ECM_NUM_CHANNELS)],
                                        "iq_power_history"      : [[] for i in range(ECM_NUM_CHANNELS)],
                                        "summary_power_mean"    : [0  for i in range(ECM_NUM_CHANNELS)],
                                        "summary_power_median"  : [0  for i in range(ECM_NUM_CHANNELS)],
                                        "summary_power_history" : [[] for i in range(ECM_NUM_CHANNELS)]}
    self.scan_seq_num += 1

    #self.pdw_processor        = pluto_esm_pdw_processor.pluto_esm_pdw_processor(logger, config)
    #self.dwell_processor      = pluto_esm_dwell_processor.pluto_esm_dwell_processor(logger, config)
    #self.pulsed_tracker       = pluto_esm_pulsed_emitter_tracker.pluto_esm_pulsed_emitter_tracker(logger, self.pdw_processor, config)
    #self.modulation_analyzer  = pluto_esm_pdw_modulation_analysis.pluto_esm_pdw_modulation_analysis(config["analysis_config"]["modulation_analysis"])
    #
    #self.confirmed_pulsed_signals_to_render     = []
    #self.confirmed_cw_primary_signals_to_render = []
    #
    #self.pending_dwell_reports        = []
    #self.pending_pdw_summary_reports  = []
    #self.pending_pdw_pulse_reports    = []
    #self.pending_combined_data        = []

    #self.emitter_update_interval = 0.1
    #self.last_emitter_update_time = 0

#  def _merge_pdws(self, combined_data):
#    dwell_report = combined_data["dwell_report"]["dwell_report"]
#    dwell_freq = combined_data["dwell_report"]["dwell_data"].frequency
#
#    for pdw in combined_data["pdw_pulse_reports"]:
#      pulse_channel = pdw["pulse_channel"]
#      pdw["channel_frequency"]      = dwell_freq + (pulse_channel - self.center_channel_index) * self.channel_spacing
#      pdw["dwell_channel_entry"]    = dwell_report["channel_data"][pulse_channel]
#      pdw["dwell_threshold_shift"]  = dwell_report["threshold_shift_narrow"]
#
#      if pdw["buffered_frame_valid"]:
#        mod_data = self.modulation_analyzer.check_intrapulse_modulation(pdw["pulse_duration"], pdw["buffered_frame_data"])
#      else:
#        mod_data = None
#      pdw["modulation_data"] = mod_data
#
#      self.recorder.log(pdw)
#
#    self.recorder.flush()
#
#  def _populate_dwell_channels(self, combined_data):
#    dwell_freq          = combined_data["dwell_report"]["dwell_data"].frequency
#    dwell_num_samples   = combined_data["dwell_report"]["dwell_report"]["num_samples"]
#    dwell_channel_data  = combined_data["dwell_report"]["dwell_report"]["channel_data"]
#    channel_mask        = combined_data["dwell_report"]["dwell_data"].hw_dwell_entry.channel_mask_narrow
#
#    num_samples_by_channel_pdw = {}
#    channel_data = {}
#
#    for i in range(ESM_NUM_CHANNELS_NARROW):
#      channel_freq = dwell_freq + (i - self.center_channel_index) * self.channel_spacing
#      if (channel_mask & (1 << i)):
#        num_samples_by_channel_pdw[channel_freq] = dwell_num_samples
#      channel_data[channel_freq] = {"accum": dwell_channel_data[i]["accum"], "max": dwell_channel_data[i]["max"]}
#
#    combined_data["dwell_num_samples_pdw"]  = num_samples_by_channel_pdw
#    combined_data["dwell_channel_data"]     = channel_data
#
#  def _process_matched_reports(self):
#    while len(self.pending_combined_data) > 0:
#      combined_data         = self.pending_combined_data.pop(0)
#      expected_pulse_count  = combined_data["pdw_summary_report"]["dwell_pulse_total_count"] - combined_data["pdw_summary_report"]["dwell_pulse_drop_count"]
#      actual_pulse_count    = len(combined_data["pdw_pulse_reports"])
#      if (expected_pulse_count != actual_pulse_count):
#        self.logger.log(self.logger.LL_WARN, "_process_matched_reports: WARNING -- pulse count mismatch: {} {}".format(expected_pulse_count, actual_pulse_count))
#        self.logger.flush()
#
#        print("_process_matched_reports: WARNING -- pulse count mismatch: {} {}".format(expected_pulse_count, actual_pulse_count))
#        #print("combined_data: {}".format(combined_data))
#      #assert (expected_pulse_count == actual_pulse_count)
#
#      self.logger.log(self.logger.LL_INFO, "[analysis_processor] _process_matched_reports: seq_num={} freq={} num_pulses={}".format(combined_data["pdw_summary_report"]["dwell_seq_num"],
#                                                                                                                                    combined_data["dwell_report"]["dwell_data"].frequency,
#                                                                                                                                    actual_pulse_count))
#      self._merge_pdws(combined_data)
#      self._populate_dwell_channels(combined_data)
#      self.pdw_processor.submit_dwell_data(combined_data)
#      self.dwell_processor.submit_dwell_data(combined_data)
#
#  def _match_dwell_reports(self):
#    if (len(self.pending_dwell_reports) == 0) or (len(self.pending_pdw_summary_reports) == 0):
#      return
#
#    pdw_seq_num   = self.pending_pdw_summary_reports[0]["pdw_summary_report"]["dwell_seq_num"]
#    dwell_seq_num = self.pending_dwell_reports[0]["dwell_report"]["dwell_seq_num"]
#
#    if pdw_seq_num != dwell_seq_num:
#      assert (pdw_seq_num > dwell_seq_num)
#      self.logger.log(self.logger.LL_WARN, "[analysis_processor] _match_dwell_reports: missed PDW dwell detected! dwell_seq_num={} pdw_seq_num={}".format(dwell_seq_num, pdw_seq_num))
#      self.pending_dwell_reports.pop(0)
#      return
#
#    matched_pulse_reports = []
#    while len(self.pending_pdw_pulse_reports) > 0:
#      pdw_dwell_seq_num = self.pending_pdw_pulse_reports[0]["pdw_pulse_report"]["dwell_seq_num"]
#      if pdw_dwell_seq_num == dwell_seq_num:
#        matched_pulse_reports.append(self.pending_pdw_pulse_reports.pop(0)["pdw_pulse_report"])
#      else:
#        if (pdw_dwell_seq_num <= dwell_seq_num):
#          print("_match_dwell_reports: out of order seq num: pdw={} dwell={}".format(pdw_dwell_seq_num, dwell_seq_num))
#        assert(pdw_dwell_seq_num > dwell_seq_num)
#        break
#
#    self.pending_combined_data.append({"dwell_report": self.pending_dwell_reports.pop(0),
#                                       "pdw_summary_report": self.pending_pdw_summary_reports.pop(0)["pdw_summary_report"],
#                                       "pdw_pulse_reports": matched_pulse_reports})
#
#  def _update_tracked_emitters(self):
#    now = time.time()
#    if (now - self.last_emitter_update_time) < self.emitter_update_interval:
#      return
#    self.last_emitter_update_time = now
#
#    self.confirmed_pulsed_signals_to_render       = copy.deepcopy(self.pulsed_tracker.confirmed_emitters)
#    self.confirmed_cw_primary_signals_to_render   = copy.deepcopy(self.dwell_processor.combined_data_primary)
#    self.confirmed_cw_secondary_signals_to_render = copy.deepcopy(self.dwell_processor.combined_data_secondary)

  def _update_scan_stats_iq(self, data):
    dwell_freq    = data["dwell_freq"]
    stats         = self.scan_stats[dwell_freq]
    iq_data       = data["iq_data"]
    channel_index = data["channel_index"]

    channel_power = np.square(np.real(iq_data)) + np.square(np.imag(iq_data))
    stats["iq_power_history"][channel_index].append(channel_power)
    stats["iq_power_mean"][channel_index]   = np.mean(stats["iq_power_history"][channel_index])
    stats["iq_power_median"][channel_index] = np.median(stats["iq_power_history"][channel_index])

    self.logger.log(self.logger.LL_DEBUG, "_update_scan_stats_iq: dwell_freq={} channel_index={} power_mean={:.1f} power_median={:.1f}".format(dwell_freq, channel_index,
      stats["iq_power_mean"][channel_index], stats["iq_power_median"][channel_index]))

  def _update_scan_stats_summary(self, data):
    dwell_freq    = data["dwell"]["dwell_data"].frequency
    channel_data  = data["dwell"]["dwell_report"]["channel_data"]
    stats         = self.scan_stats[dwell_freq]

    for channel_index in range(ECM_NUM_CHANNELS):
      channel_entry = channel_data[channel_index]
      channel_power = channel_entry["accum"] / channel_entry["cycles"]

      stats["summary_power_history"][channel_index].append(channel_power)
      stats["summary_power_mean"][channel_index]    = np.mean(stats["summary_power_history"][channel_index])
      stats["summary_power_median"][channel_index]  = np.median(stats["summary_power_history"][channel_index])

    self.logger.log(self.logger.LL_DEBUG, "_update_scan_stats_summary: freq={}".format(dwell_freq))

  def _process_report_for_iq(self, data):
    now = time.time()
    if (now - self.iq_stats_time) > 1.0:
      self.logger.log(self.logger.LL_INFO, "_process_report_for_iq: count={} samples={}".format(self.iq_stats_count, self.iq_stats_samples))
      self.iq_stats_time = now
      self.iq_stats_count = 0
      self.iq_stats_samples = 0

    self.iq_stats_count += 1
    self.iq_stats_samples += len(data["iq_data"])

    result = self.process_pool.apply_async(self.mod_analysis.process_iq_data, (data,))
    self.pool_results.append(result)
    #self.mod_analysis.process_iq_data(data["iq_data"])

  @staticmethod
  def _iq_to_complex(data):
    data_c = [data[i][0] + 1j * data[i][1] for i in range(len(data))]
    return np.asarray(data_c, dtype=np.complex64)

  @staticmethod
  def _remove_dc_offset(data):
    return data - np.mean(data, 0)

  @staticmethod
  def _apply_basebanding(data):
    data[0:-1:2] *= -1
    return data

  def _process_scan_reports(self):
    while len(self.pending_scan_reports_iq) > 0:
      report = self.pending_scan_reports_iq.pop(0)
      d = report["scan_report_iq"]
      dwell_freq = d["dwell"]["dwell_data"].frequency
      channel_reports = d["drfm_channel_reports"]
      channel_index = channel_reports[0]["channel_index"]
      scan_data = []
      iq_data = []
      for i in range(len(channel_reports)):
        r = channel_reports[i]
        if (r["channel_index"] != channel_index):
          scan_data.append({"sw_timestamp": report["timestamp"], "controller_state": report["state"], "dwell_freq": dwell_freq, "channel_index": channel_index, "hw_timestamp": r["segment_timestamp"], "iq_length": len(iq_data), "iq_data": np.asarray(iq_data)})
          iq_data = []
          channel_index = r["channel_index"]

        iq_data.extend(self._iq_to_complex(r["iq_data"]))
      scan_data.append({"sw_timestamp": report["timestamp"], "controller_state": report["state"], "dwell_freq": dwell_freq, "channel_index": channel_index, "hw_timestamp": r["segment_timestamp"], "iq_length": len(iq_data), "iq_data": np.asarray(iq_data)})

      for sd in scan_data:
        sd["iq_data"] = self._remove_dc_offset(sd["iq_data"])
        if sd["channel_index"] % 2 == 1:
          sd["iq_data"] = self._apply_basebanding(sd["iq_data"])

        if sd["controller_state"] == "SCAN":
          self._update_scan_stats_iq(sd)
        elif sd["controller_state"] == "TX_LISTEN":
          self._process_report_for_iq(sd)

        #sd_rec = copy.deepcopy(sd)
        #r_iq = [[float(np.real(sd_rec["iq_data"][i])), float(np.imag(sd_rec["iq_data"][i]))] for i in range(sd_rec["iq_data"].shape[0])]
        #sd_rec["iq_data"] = r_iq
        #self.recorder.log(sd_rec)

      if report["state"] == "SCAN":
        self._update_scan_stats_summary(d)

    while len(self.pending_scan_reports_bare) > 0:
      report = self.pending_scan_reports_bare.pop(0)
    #  if report["state"] == "SCAN":
    #    d = report["scan_report_bare"]
    #    dwell_freq = d["dwell"]["dwell_data"].frequency
    #    print("[scan] bare report: {}".format(dwell_freq))

    #
    #  scan_data.append({"controller_state": d["state"], "dwell_freq": dwell_freq, "channel_index": channel_index, "iq_length": len(iq_data), "iq_data": np.asarray(iq_data)})

  def _process_pool_results(self):
    while len(self.pool_results) > 0:
      if not self.pool_results[0].ready():
        break
      result = self.pool_results[0].get()

      #print("pool result ready at {}: {}".format(time.time(), result))
      self.recorder.log(result)
      self.pool_results.pop(0)


  def _process_command(self, data):
    command = data["command"]

    if command == "SCAN_START":
      self._clear_scan_stats()
    elif command == "SCAN_END":
      for freq in self.scan_stats:
        self.logger.log(self.logger.LL_DEBUG, "_process_command: SCAN_END: iq_power_mean[{}]        ={}".format(freq, self.scan_stats[freq]["iq_power_mean"]))
        self.logger.log(self.logger.LL_DEBUG, "_process_command: SCAN_END: iq_power_median[{}]      ={}".format(freq, self.scan_stats[freq]["iq_power_median"]))
        self.logger.log(self.logger.LL_DEBUG, "_process_command: SCAN_END: summary_power_mean[{}]   ={}".format(freq, self.scan_stats[freq]["summary_power_mean"]))
        self.logger.log(self.logger.LL_DEBUG, "_process_command: SCAN_END: summary_power_median[{}] ={}".format(freq, self.scan_stats[freq]["summary_power_median"]))
        self.output_queue.put({"scan_results": {"freq": freq,
                                                "iq_power_mean"       : self.scan_stats[freq]["iq_power_mean"],
                                                "iq_power_median"     : self.scan_stats[freq]["iq_power_median"],
                                                "summary_power_mean"  : self.scan_stats[freq]["summary_power_mean"],
                                                "summary_power_median": self.scan_stats[freq]["summary_power_median"]}})
      self.output_queue.put({"scan_seq_num": self.scan_seq_num})
    else:
      raise RuntimeError("unknown command")

  def submit_data(self, data):
    if "scan_report_iq" in data:
      self.pending_scan_reports_iq.append(data)
    elif "scan_report_bare" in data:
      self.pending_scan_reports_bare.append(data)

    elif "tx_report" in data:
      self.pending_tx_reports.append(data)
    elif "command" in data:
      self._process_command(data)
    else:
      raise RuntimeError("invalid report")

  def update(self):
    #self.dwell_processor.update()
    #self.pdw_processor.update()
    #self.pulsed_tracker.update()
    #self._match_dwell_reports()
    #self._process_matched_reports()
    #self._update_tracked_emitters()
    self._process_scan_reports()
    self._process_pool_results()

  def shutdown(self, reason):
    self.recorder.shutdown(reason)
