from pluto_intercept_hw_pkg import *
import time
import numpy as np

class pluto_intercept_signal_tracker:
  def __init__(self, logger, config, frequency_db):
    self.logger = logger
    self.config = config

    self.frequency_table          = frequency_db["frequency_table"]
    self.signal_update_interval   = config["signal_tracker"]["update_interval"]
    self.max_report_age           = config["signal_tracker"]["max_report_age"]
    self.max_signal_age           = config["signal_tracker"]["max_signal_age"]
    self.max_freq_diff            = config["signal_tracker"]["max_freq_diff"] * 1e-3

    self.last_update_time         = 0
    self.pending_analysis_reports = []
    self.tracked_signals          = []

    #TODO: cleanup

    #output_entry = {"timestamp_conv_end"  : now,
    #                "stream_index"        : stream_index,
    #                "channel_index"       : self.stream_buffer_channel[stream_index],
    #                "dwell_frequency"     : self.stream_buffer_dwell_freq[stream_index],
    #                "center_frequency"    : self._get_center_frequency(self.stream_buffer_dwell_freq[stream_index], self.stream_buffer_channel[stream_index], downconverted_data[i]["lo_frequency"]),
    #                "lo_index"            : downconverted_data[i]["lo_index"],
    #                "lo_frequency"        : downconverted_data[i]["lo_frequency"],
    #                "iq_data"             : downconverted_data[i]["iq_data"],
    #                "fs"                  : downconverted_data[i]["fs"]}

    #r["iq_data_I"] = iq_data.real
    #r["iq_data_Q"] = iq_data.imag
    #
    #features = {}
    #features["power_avg"]             = iq_power_avg
    #features["power_peak"]            = iq_power_peak
    #features["power_papr"]            = iq_power_peak / iq_power_avg
    #features["amplitude_mean"]        = iq_amplitude_mean
    #features["amplitude_median"]      = iq_amplitude_qtls[1]
    #features["amplitude_std"]         = iq_amplitude_std
    #features["amplitude_cv"]          = iq_amplitude_std / iq_amplitude_mean
    #features["amplitude_hist_count"]  = amplitude_hist_count
    #features["amplitude_hist_edges"]  = amplitude_hist_edges
    #features["amplitude_iqr_ratio"]   = (iq_amplitude_qtls[2] - iq_amplitude_qtls[0]) / iq_amplitude_qtls[1]
    #features["frequency_mean"]        = iq_freq_mean
    #features["frequency_std"]         = iq_freq_std
    #features["frequency_hist_count"]  = frequency_hist_count
    #features["frequency_hist_edges"]  = frequency_hist_edges
    #features["bandwidth_3dB"]         = bandwidth[0]
    #features["bandwidth_6dB"]         = bandwidth[1]
    #features["bandwidth_10dB"]        = bandwidth[2]
    #features["iq_acorr_abs"]          = iq_data_acorr_abs
    #features["frequency_acorr_abs"]   = iq_freq_acorr_abs
    #
    ##features["frequency_data"]        = iq_freq #TODO: remove
    #
    #r["timestamp_proc_start"] = t_start
    #r["timestamp_proc_end"] = time.time()
    #r["features"] = features

  def _get_signal_name(self, frequency):
    name = "unknown"

    for entry in self.frequency_table:
      if "range" in entry:
        freq_range = entry["range"]
        if (frequency >= freq_range[0]) and (frequency < freq_range[1]):
          name = entry["name"]

      elif "frequency" in entry:
        freq_range = [entry["frequency"] - entry["bandwidth"] * 1e-3, entry["frequency"] + entry["bandwidth"] * 1e-3]
        if (frequency >= freq_range[0]) and (frequency < freq_range[1]):
          name = entry["name"]

      else:
        raise RuntimeError("invalid entry")

    return name

  def _update_signals(self):
    while len(self.pending_analysis_reports) > 0:
      report = self.pending_analysis_reports.pop(0)
      tracked_freqs = np.asarray([e["center_frequency"] for e in self.tracked_signals])

      if tracked_freqs.size > 0:
        freq_diff = np.abs(tracked_freqs - report["center_frequency"])
        closest_i = np.argmin(freq_diff)
        if freq_diff[closest_i] < self.max_freq_diff:
          self._update_signal(closest_i, report)
        else:
          self._initialize_signal(report)
      else:
        self._initialize_signal(report)

  def _scrub_signals(self):
    now = time.time()

    signals_to_keep = []
    for entry in self.tracked_signals:
      reports = entry["reports"]
      while len(reports) > 1:
        if (now - reports[0]["timestamp_conv_end"]) > self.max_report_age:
          reports.pop(0)
        else:
          break

      if (len(reports) > 0) and ((now - reports[0]["timestamp_conv_end"]) < self.max_signal_age):
        signals_to_keep.append(entry)
      else:
        self.logger.log(self.logger.LL_INFO, "[signal_tracker] _scrub_emitters: signal timeout - freq={} - reports={}".format(entry["center_frequency"], len(reports)))

    self.tracked_signals = signals_to_keep

  def _initialize_signal(self, report):
    s = { "center_frequency"    : report["center_frequency"],
          "name"                : self._get_signal_name(report["center_frequency"]),
          "power_mean"          : report["features"]["power_avg"],
          "power_max"           : report["features"]["power_peak"],
          "reports"             : [report],
          "timestamp_initial"   : report["timestamp_conv_end"],
          "timestamp_final"     : report["timestamp_conv_end"],
          "processing_delay"    : time.time() - report["timestamp_conv_end"]
        }

    self.logger.log(self.logger.LL_INFO, "[signal_tracker] _initialize_signal: new signal added: freq={:.3f}".format(s["center_frequency"]))
    self.tracked_signals.append(s)

  def _update_signal(self, tracked_index, report):
    now = time.time()
    tracked_signal = self.tracked_signals[tracked_index]

    tracked_signal["timestamp_final"] = report["timestamp_conv_end"]
    tracked_signal["processing_delay"] = now - report["timestamp_conv_end"]
    tracked_signal["reports"].append(report)

    freq_data       = [r["center_frequency"]        for r in tracked_signal["reports"]]
    power_mean_data = [r["features"]["power_avg"]   for r in tracked_signal["reports"]]
    power_max_data  = [r["features"]["power_peak"]  for r in tracked_signal["reports"]]

    tracked_signal["center_frequency"]  = np.mean(freq_data)
    tracked_signal["power_mean"]        = np.mean(power_mean_data)
    tracked_signal["power_max"]         = np.max(power_max_data)

    tracked_signal["name"] = self._get_signal_name(tracked_signal["center_frequency"])

    #TODO: bandwidth
    #TODO: signal type

  def submit_analysis_report(self, report):
    self.pending_analysis_reports.append(report)

  def get_tracked_signals(self):
    return self.tracked_signals

  def update(self):
    now = time.time()
    if (now - self.last_update_time) < self.signal_update_interval:
      return
    self.last_update_time = now

    self._update_signals()
    self._scrub_signals()
