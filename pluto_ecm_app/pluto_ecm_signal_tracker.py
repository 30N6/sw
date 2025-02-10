from pluto_ecm_hw_pkg import *
import time
import numpy as np

class pluto_ecm_signal_tracker:
  def __init__(self, logger, config):
    self.logger = logger
    self.config = config

    self.channel_bandwidth = (ADC_CLOCK_FREQUENCY / ECM_NUM_CHANNELS) / 1e6

    #self.pdw_processor = pdw_processor
    #self.pulsed_emitter_config        = config["emitter_config"]["pulsed_emitters"]
    #self.modulation_threshold         = config["analysis_config"]["pulsed_emitter_config"]["modulation_threshold"]
    #self.pd_range_scaling             = config["analysis_config"]["pulsed_emitter_config"]["PW_range_scaling"]
    #self.pri_range_scaling            = config["analysis_config"]["pulsed_emitter_config"]["PRI_range_scaling"]
    #self.expected_pulse_count_factor  = config["analysis_config"]["pulsed_emitter_config"]["expected_pulse_count_factor"]
    #self.min_matched_pulses           = config["analysis_config"]["pulsed_emitter_config"]["min_matched_pulses"]
    #
    #self.max_pdw_age_to_confirm       = config["analysis_config"]["pulsed_emitter_config"]["max_pdw_age_to_confirm"]
    #self.emitter_update_interval      = config["analysis_config"]["pulsed_emitter_config"]["emitter_update_interval"]

    self.signal_update_interval        = config["analysis_config"]["signal_tracker"]["update_interval"]
    self.max_report_age                = config["analysis_config"]["signal_tracker"]["max_report_age"]
    self.max_signal_age                = config["analysis_config"]["signal_tracker"]["max_signal_age"]

    self.last_update_time = 0

    self.pending_analysis_reports = []

    #self.matched_analysis_reports = {}
    #for mod_type in config["analysis_config"]["modulation_analysis"]:
    #  self.matched_analysis_reports[mod_type] = []

    self.confirmed_signals = []

  def submit_analysis_report(self, report):
    self.pending_analysis_reports.append(report)

  def update(self):
    now = time.time()
    if (now - self.last_update_time) < self.signal_update_interval:
      return
    self.last_update_time = now

    self._search_for_signals()
    self._scrub_signals()

  def _search_for_signals(self):
    while len(self.pending_analysis_reports) > 0:
      report = self.pending_analysis_reports.pop(0)
      analysis_data = report["analysis"]

      for mod_type, mod_config in self.config["analysis_config"]["modulation_analysis"].items():
        matched_criteria = {}

        for config_key, config_entry in mod_config["criteria"].items():
          matched_criteria[config_key] = (analysis_data[config_key] >= config_entry[0]) and (analysis_data[config_key] <= config_entry[1])

        if all(matched_criteria.values()):
          self._update_confirmed_signals(report, mod_type, mod_config)
          break

  def _scrub_signals(self):
    now = time.time()
    signals_to_keep = []

    for entry in self.confirmed_signals:
      reports = entry["reports"]
      while len(reports) > 0:
        if (now - reports[0]["timestamp"]) > self.max_report_age:
          reports.pop(0)
        else:
          break

      if (len(reports) > 0) and ((now - reports[0]["timestamp"]) < self.max_signal_age):
        signals_to_keep.append(entry)
        #self.logger.log(self.logger.LL_INFO, "[signal_tracker] _scrub_emitters: keeping emitter {}".format(entry))
      else:
        self.logger.log(self.logger.LL_INFO, "[signal_tracker] _scrub_emitters: confirmed signal timeout - {}".format(entry))

    self.confirmed_signals = signals_to_keep

  def _update_confirmed_signals(self, report, mod_type, mod_entry):
    channel_edge = [report["channel_freq"] - (self.channel_bandwidth/2), report["channel_freq"] + (self.channel_bandwidth/2)]

    signal_matched = False
    for signal_entry in self.config["tx_config"]["signals"]:
      #if signal_entry["name"] == "ARSR":
      #  print(signal_entry)
      #  print("report: {} {} {}".format(channel_edge[0], channel_edge[1], report["analysis"]["iq_length"]))

      if mod_type != signal_entry["trigger_modulation"]:
        continue
      if channel_edge[1] < signal_entry["freq_range"][0]:
        continue
      if channel_edge[0] > signal_entry["freq_range"][1]:
        continue
      if report["analysis"]["iq_length"] < signal_entry["trigger_duration"][0]:
        continue
      if report["analysis"]["iq_length"] > signal_entry["trigger_duration"][1]:
        continue
      signal_matched = True
      break

    if not signal_matched:
      return

    confirmed_match = False
    for confirmed_entry in self.confirmed_signals:
      if signal_entry["name"] != confirmed_entry["name"]:
        continue

      if signal_entry["agile"]:
        if confirmed_entry["freq"] != report["dwell_freq"]:
          continue
      else:
        if confirmed_entry["freq"] != report["channel_freq"]:
          continue

      confirmed_match = True
      break

    if confirmed_match:
      self._update_confirmed_signal(confirmed_entry, report)
    else:
      self.confirmed_signals.append(self._initialize_confirmed_signal(signal_entry, report, mod_entry["display_metric"]))

  def _update_confirmed_signal(self, confirmed_entry, report):
    new_report_entry = {"dwell_freq"    : report["dwell_freq"],
                        "channel_freq"  : report["channel_freq"],
                        "timestamp"     : report["sw_timestamp"],
                        "analysis"      : report["analysis"]}

    confirmed_entry["timestamp_final"] = report["sw_timestamp"]
    confirmed_entry["reports"].append(new_report_entry)
    confirmed_entry["stats"] = self._update_signal_stats(confirmed_entry)

    max_report_age = time.time() - confirmed_entry["reports"][0]["timestamp"]
    self.logger.log(self.logger.LL_INFO, "[signal_tracker] _update_confirmed_signal: name={} freq={} max_report_age={:.1f}  report={}".format(confirmed_entry["name"], confirmed_entry["freq"], max_report_age, new_report_entry))

  def _initialize_confirmed_signal(self, signal_entry, report, display_metric):
    if signal_entry["agile"]:
      freq = report["dwell_freq"]
    else:
      freq = report["channel_freq"]

    new_report_entry = {"dwell_freq"    : report["dwell_freq"],
                        "channel_freq"  : report["channel_freq"],
                        "timestamp"     : report["sw_timestamp"],
                        "analysis"      : report["analysis"]}

    signal = {"freq"                : freq,
              "name"                : signal_entry["name"],
              "reports"             : [new_report_entry],
              "display_metric_name" : display_metric,
              "timestamp_initial"   : report["sw_timestamp"],
              "timestamp_final"     : report["sw_timestamp"]}

    signal["stats"] = self._update_signal_stats(signal)

    self.logger.log(self.logger.LL_INFO, "[signal_tracker] _initialize_confirmed_signal: new signal added: name={} freq={} report={}".format(signal_entry["name"], freq, new_report_entry))

    return signal

  def _update_signal_stats(self, entry):
    display_metric_name = entry["display_metric_name"]

    power       = [r["analysis"]["power_mean"]        for r in entry["reports"]]
    duration    = [r["analysis"]["iq_length"]         for r in entry["reports"]]
    disp_metric = [r["analysis"][display_metric_name] for r in entry["reports"]]

    stats = {"power_mean"           : np.mean(power),
             "power_max"            : np.max(power),
             "power_std"            : np.std(power),
             "duration_mean"        : np.mean(duration),
             "duration_max"         : np.max(duration),
             "duration_std"         : np.std(duration),
             "display_metric_mean"  : np.mean(disp_metric),
             "report_count"         : len(entry["reports"])}
    return stats
