import time
import numpy as np
import copy
import multiprocessing
import traceback

from pluto_ecm_hw_pkg import *
import pluto_ecm_data_recorder
import pluto_ecm_modulation_analysis
import pluto_ecm_signal_tracker

class pluto_ecm_analysis_processor:
  def __init__(self, logger, log_dir, config, output_queue):
    self.logger       = logger
    self.recorder     = pluto_ecm_data_recorder.pluto_ecm_data_recorder(log_dir, "analysis", 1) #config["analysis_config"]["enable_pdw_recording"])
    self.config       = config
    self.output_queue = output_queue

    self.mod_analysis   = pluto_ecm_modulation_analysis.pluto_ecm_modulation_analysis(config)
    self.signal_tracker = pluto_ecm_signal_tracker.pluto_ecm_signal_tracker(logger, config)

    self.center_channel_index = (ECM_NUM_CHANNELS // 2)
    self.channel_spacing      = (ADC_CLOCK_FREQUENCY / ECM_NUM_CHANNELS) / 1e6

    self.signal_update_interval     = config["analysis_config"]["signal_tracker"]["update_interval"]
    self.last_update_time           = 0

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

    self.data_to_render = []
    self.signal_processing_delay = 0

  def _clear_scan_stats(self):
    for entry in self.config["dwell_config"]["dwell_freqs"]:
      self.scan_stats[entry["freq"]] = {"iq_power_mean"         : [0  for i in range(ECM_NUM_CHANNELS)],
                                        "iq_power_median"       : [0  for i in range(ECM_NUM_CHANNELS)],
                                        "iq_power_history"      : [[] for i in range(ECM_NUM_CHANNELS)],
                                        "summary_power_mean"    : [0  for i in range(ECM_NUM_CHANNELS)],
                                        "summary_power_median"  : [0  for i in range(ECM_NUM_CHANNELS)],
                                        "summary_power_history" : [[] for i in range(ECM_NUM_CHANNELS)]}
    self.scan_seq_num += 1

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

  def _get_channel_freq(self, dwell_freq, channel_index):
    return dwell_freq + (channel_index - self.center_channel_index) * self.channel_spacing

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
          scan_data.append({"sw_timestamp": report["timestamp"], "controller_state": report["state"],
                            "dwell_freq": dwell_freq, "channel_index": channel_index, "channel_freq": self._get_channel_freq(dwell_freq, channel_index),
                            "hw_timestamp": r["segment_timestamp"], "iq_length": len(iq_data), "iq_data": np.asarray(iq_data)})
          iq_data = []
          channel_index = r["channel_index"]

        iq_data.extend(self._iq_to_complex(r["iq_data"]))
      scan_data.append({"sw_timestamp": report["timestamp"], "controller_state": report["state"],
                        "dwell_freq": dwell_freq, "channel_index": channel_index, "channel_freq": self._get_channel_freq(dwell_freq, channel_index),
                        "hw_timestamp": r["segment_timestamp"], "iq_length": len(iq_data), "iq_data": np.asarray(iq_data)})

      for sd in scan_data:
        sd["iq_data"] = self._remove_dc_offset(sd["iq_data"])
        if sd["channel_index"] % 2 == 1:
          sd["iq_data"] = self._apply_basebanding(sd["iq_data"])

        if sd["controller_state"] == "SCAN":
          self._update_scan_stats_iq(sd)
          self._process_report_for_iq(sd)

        elif sd["controller_state"] == "TX_LISTEN":
          self._process_report_for_iq(sd)

        elif sd["controller_state"] == "TX_ACTIVE":
          self._process_report_for_iq(sd)

        #sd_rec = copy.deepcopy(sd)
        #r_iq = [[float(np.real(sd_rec["iq_data"][i])), float(np.imag(sd_rec["iq_data"][i]))] for i in range(sd_rec["iq_data"].shape[0])]
        #sd_rec["iq_data"] = r_iq
        #self.recorder.log(sd_rec)

      if report["state"] == "SCAN":
        self._update_scan_stats_summary(d)

    while len(self.pending_scan_reports_bare) > 0:
      report = self.pending_scan_reports_bare.pop(0)
      #TODO: remove?
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

      self.signal_tracker.submit_analysis_report(result)
      self.signal_processing_delay = time.time() - result["sw_timestamp"]
      #if (result["controller_state"] == "SCAN"):
      #  print("pool result ready at {}: {}".format(time.time(), result))

      self.recorder.log(result)
      self.pool_results.pop(0)

  def _copy_tracked_signals(self):
    now = time.time()
    if (now - self.last_update_time) < self.signal_update_interval:
      return
    self.last_update_time = now

    confirmed_signals = []
    scan_signals = []

    for entry in self.signal_tracker.confirmed_signals:
      copied_entry = {"freq"              : entry["freq"],
                      "name"              : entry["name"],
                      "stats"             : copy.deepcopy(entry["stats"]),
                      "timestamp_initial" : entry["timestamp_initial"],
                      "timestamp_final"   : entry["timestamp_final"],
                      "processing_delay"  : entry["processing_delay"]}

      confirmed_signals.append(copied_entry)

    for entry in self.signal_tracker.scan_signals:
      copied_entry = {"freq"              : entry["freq"],
                      "name"              : entry["name"],
                      "stats"             : copy.deepcopy(entry["stats"]),
                      "timestamp_initial" : entry["timestamp_initial"],
                      "timestamp_final"   : entry["timestamp_final"],
                      "processing_delay"  : entry["processing_delay"]}

      scan_signals.append(copied_entry)

    self.data_to_render = []
    if len(confirmed_signals) > 0:
      self.data_to_render.append({"confirmed_signals": confirmed_signals})
    if len(scan_signals) > 0:
      self.data_to_render.append({"scan_signals": scan_signals})

    self.data_to_render.append({"signal_processing_delay": self.signal_processing_delay})

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

    try:
      self._process_scan_reports()
      self._process_pool_results()
      self.signal_tracker.update()
      self._copy_tracked_signals()
    except Exception:
      print(traceback.format_exc())

  def shutdown(self, reason):
    self.recorder.shutdown(reason)
