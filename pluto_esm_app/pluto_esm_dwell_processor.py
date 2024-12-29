from pluto_esm_hw_pkg import *
import time
import numpy as np

class pluto_esm_dwell_processor:
  def __init__(self, logger, config):
    self.logger = logger
    self.config = config

    self.channel_data_history     = {}
    self.channel_data_summary     = {}
    self.threshold_data           = {}
    self.detection_data_primary   = {}
    self.detection_data_secondary = {}
    self.combined_data_primary    = []
    self.combined_data_secondary  = []

    self.max_dwell_age        = config["analysis_config"]["cw_emitter_config"]["max_dwell_age"]
    self.max_signal_age       = config["analysis_config"]["cw_emitter_config"]["max_signal_age"]
    self.threshold_factor     = 10 ** (config["analysis_config"]["cw_emitter_config"]["auto_threshold_factor_dB"] / 10) # TODO: different by frequency?
    self.threshold_min        = 10 ** (config["analysis_config"]["cw_emitter_config"]["auto_threshold_min_dB"] / 10)
    self.num_dwells_required  = config["analysis_config"]["cw_emitter_config"]["num_dwells_required"]

    self.channel_sample_factor = ESM_NUM_CHANNELS_NARROW / CHANNELIZER_OVERSAMPLING

  def submit_dwell_data(self, combined_dwell_data):
    now = time.time()
    num_channel_samples = combined_dwell_data["dwell_report"]["dwell_report"]["num_samples"] // self.channel_sample_factor

    for freq in combined_dwell_data["dwell_channel_data"]:
      entry = combined_dwell_data["dwell_channel_data"][freq]

      new_entry = {"timestamp": now, "channel_samples": num_channel_samples, "accum_normalized": entry["accum"] / num_channel_samples, "max": entry["max"]}

      if freq not in self.channel_data_history:
        self.channel_data_history[freq] = []
      self.channel_data_history[freq].append(new_entry)

      while (len(self.channel_data_history[freq]) > 0) and ((now - self.channel_data_history[freq][0]["timestamp"]) > self.max_dwell_age):
        self.channel_data_history[freq].pop(0)

      accum_list  = np.asarray([d["accum_normalized"] for d in self.channel_data_history[freq]])
      max_list    = np.asarray([d["max"] for d in self.channel_data_history[freq]])
      self.channel_data_summary[freq] = {"accum_list": accum_list, "max_list": max_list, "accum_mean": np.mean(accum_list), "accum_median": np.median(accum_list), "accum_std": np.std(accum_list)}

      self._update_threshold(freq)
      self._update_detection(freq, new_entry)

    self._merge_signals_primary(list(combined_dwell_data["dwell_channel_data"].keys()))
    self._merge_signals_secondary(list(combined_dwell_data["dwell_channel_data"].keys()))

      #self.logger.log(self.logger.LL_INFO, "[dwell_processor] freq={} summary: mean={} accum={} -- threshold={}/{}".format(freq, new_entry["accum_normalized"], self.channel_data_summary[freq]["accum_mean"],
      #  self.threshold_data[freq]["threshold_0_data"], self.threshold_data[freq]["threshold_1_data"]))

  def _try_get_manual_threshold(self, freq):
    matching_entry = None

    for entry in self.config["emitter_config"]["cw_emitters"]:
      if "manual_threshold_mean_dB" not in entry:
        continue
      if (freq < entry["freq_range"][0]) or (freq > entry["freq_range"][1]):
        continue
      if (matching_entry is None) or (entry["manual_threshold_mean_dB"] < entry["manual_threshold_mean_dB"]):
        matching_entry = entry

    if matching_entry is not None:
      return True, 10 ** (matching_entry["manual_threshold_mean_dB"] / 10)
    else:
      return False, None

  def _update_threshold(self, freq):
    if freq not in self.threshold_data:
      self.threshold_data[freq] = {"threshold_0_data": 0, "threshold_1_data": 0, "threshold_factor": 0, "threshold_valid": False, "manual_threshold_data": 0, "manual_threshold_valid": False}
      self.threshold_data[freq]["manual_threshold_valid"], self.threshold_data[freq]["manual_threshold_data"] = self._try_get_manual_threshold(freq)
      if self.threshold_data[freq]["manual_threshold_valid"]:
        self.logger.log(self.logger.LL_INFO, "[dwell_processor] _update_threshold: new freq={:.2f} - manual_threshold={:.3f}".format(freq, self.threshold_data[freq]["manual_threshold_data"]))

    if (not self.threshold_data[freq]["threshold_valid"]) and (len(self.channel_data_history[freq]) >= self.num_dwells_required):
      self.threshold_data[freq]["threshold_valid"] = True
      self.threshold_data[freq]["threshold_factor"] = self.threshold_factor
      self.threshold_data[freq]["threshold_min"]    = self.threshold_min
      self.threshold_data[freq]["threshold_0_data"] = self.threshold_data[freq]["threshold_factor"] * self.channel_data_summary[freq]["accum_mean"]

    if self.threshold_data[freq]["threshold_valid"]:
      self.threshold_data[freq]["threshold_0_data"] = np.minimum(self.threshold_data[freq]["threshold_factor"] * self.channel_data_summary[freq]["accum_mean"], self.threshold_data[freq]["threshold_0_data"])
      self.threshold_data[freq]["threshold_1_data"] = self.threshold_data[freq]["threshold_factor"] * self.channel_data_summary[freq]["accum_mean"]

  def _update_detection(self, freq, dwell_entry):
    if self.threshold_data[freq]["threshold_valid"]:
      detect_0    = dwell_entry["accum_normalized"] > self.threshold_data[freq]["threshold_0_data"]
      detect_1    = dwell_entry["accum_normalized"] > self.threshold_data[freq]["threshold_1_data"]
      detect_min  = dwell_entry["accum_normalized"] > self.threshold_data[freq]["threshold_min"]
      detection_level = (int(detect_0) + int(detect_1)) * int(detect_min)
    else:
      detection_level = 0

    detect_manual = self.threshold_data[freq]["manual_threshold_valid"] and (dwell_entry["accum_normalized"] > self.threshold_data[freq]["manual_threshold_data"])

    now = time.time()

    if detection_level > 0:
      if freq not in self.detection_data_primary:
        self.detection_data_primary[freq] = {"num_dwells": 0, "detection_level": 0, "time_initial": now, "time_final": 0}
        self.logger.log(self.logger.LL_INFO, "[dwell_processor] [primary] new signal: freq={:.2f} detection_level={} power={:.3f} -- thresholds={:.3f}/{:.3f}".format(freq, detection_level, dwell_entry["accum_normalized"],
          self.threshold_data[freq]["threshold_0_data"], self.threshold_data[freq]["threshold_1_data"]))

      self.detection_data_primary[freq]["power_threshold"]  = np.minimum(self.threshold_data[freq]["threshold_0_data"], self.threshold_data[freq]["threshold_1_data"])
      self.detection_data_primary[freq]["power_mean"]       = dwell_entry["accum_normalized"]
      self.detection_data_primary[freq]["power_max"]        = dwell_entry["max"]
      self.detection_data_primary[freq]["num_dwells"]       += 1
      self.detection_data_primary[freq]["detection_level"]  = detection_level
      self.detection_data_primary[freq]["time_final"]       = now

    elif freq in self.detection_data_primary:
      if (now - self.detection_data_primary[freq]["time_final"]) > self.max_signal_age:
        self.detection_data_primary.pop(freq, None)
        self.logger.log(self.logger.LL_INFO, "[dwell_processor] [primary] stale signal removed: freq={}".format(freq))

    if detect_manual:
      if freq not in self.detection_data_secondary:
        self.detection_data_secondary[freq] = {"num_dwells": 0, "time_initial": now, "time_final": 0}
        self.logger.log(self.logger.LL_INFO, "[dwell_processor] [secondary] new signal: freq={:.2f} power={:.3f} threshold={:.3f}".format(freq, dwell_entry["accum_normalized"], self.threshold_data[freq]["manual_threshold_data"]))

      self.detection_data_secondary[freq]["power_threshold"]  = self.threshold_data[freq]["manual_threshold_data"]
      self.detection_data_secondary[freq]["power_mean"]       = dwell_entry["accum_normalized"]
      self.detection_data_secondary[freq]["power_max"]        = dwell_entry["max"]
      self.detection_data_secondary[freq]["num_dwells"]       += 1
      self.detection_data_secondary[freq]["time_final"]       = now

    elif freq in self.detection_data_secondary:
      if (now - self.detection_data_secondary[freq]["time_final"]) > self.max_signal_age:
        self.detection_data_secondary.pop(freq, None)
        self.logger.log(self.logger.LL_INFO, "[dwell_processor] [secondary] stale signal removed: freq={}".format(freq))

  def _merge_signals_secondary(self, freqs):
    for freq in freqs:
      if freq not in self.detection_data_secondary:
        continue

      found = False
      for entry in self.combined_data_secondary:
        if freq in entry["freq_set"]:
          found = True
          break

      if not found:
        entry = {"freq_set": set([freq]), "detection_data": {}, "power_mean_value": 0, "power_mean_freq": 0, "power_mean_threshold": 0, "power_max": 0, "num_dwells": 0, "time_initial": np.inf, "time_final": 0}
        self.combined_data_secondary.append(entry)

      entry["detection_data"][freq] = self.detection_data_secondary[freq]
      self._update_combined_data(entry, self.detection_data_secondary)

  def _merge_signals_primary(self, freqs):
    detection_valid = [f in self.detection_data_primary for f in freqs]

    combined_freqs = []
    current_freqs = []
    active = False
    for i in range(len(freqs)):
      if detection_valid[i]:
        active = True
        current_freqs.append(freqs[i])
      elif active:
        active = False
        combined_freqs.append(current_freqs)
        current_freqs = []

    if active:
      combined_freqs.append(current_freqs)

    for freq_list in combined_freqs:
      found = False
      for entry in self.combined_data_primary:
        if not entry["freq_set"].isdisjoint(freq_list):
          found = True
          break

      if found:
        entry["freq_set"].update(freq_list)
      else:
        entry = {"freq_set": set(freq_list), "detection_data": {}, "power_mean_value": 0, "power_mean_freq": 0, "power_mean_threshold": 0, "power_max": 0, "num_dwells": 0, "time_initial": np.inf, "time_final": 0}
        self.combined_data_primary.append(entry)

      for freq in freq_list:
        entry["detection_data"][freq] = self.detection_data_primary[freq]
      self._update_combined_data(entry, self.detection_data_primary)

  def _update_combined_data(self, emitter_entry, detection_data):
    for freq in emitter_entry["freq_set"]:
      if freq not in detection_data:
        continue

      freq_det_data = detection_data[freq]

      emitter_entry["time_initial"] = min(emitter_entry["time_initial"],  freq_det_data["time_initial"])
      emitter_entry["time_final"]   = max(emitter_entry["time_final"],    freq_det_data["time_final"])
      emitter_entry["num_dwells"]   = max(emitter_entry["num_dwells"],    freq_det_data["num_dwells"])
      emitter_entry["power_max"]    = max(emitter_entry["power_max"],     freq_det_data["power_max"])

      if freq_det_data["power_mean"] > emitter_entry["power_mean_value"]:
        emitter_entry["power_mean_freq"]      = freq
        emitter_entry["power_mean_value"]     = freq_det_data["power_mean"]
        emitter_entry["power_mean_threshold"] = freq_det_data["power_threshold"]

  def _scrub_combined_data(self, combined_data, detection_data):
    now = time.time()

    valid_signals = []
    for entry in combined_data:
      freqs = list(entry["detection_data"].keys())
      for freq in freqs:
        if (now - entry["detection_data"][freq]["time_final"]) > self.max_signal_age:
          entry["detection_data"].pop(freq)
          entry["freq_set"].remove(freq)

      if len(entry["freq_set"]) > 0:
        self._update_combined_data(entry, detection_data)
        valid_signals.append(entry)

    combined_data.clear()
    combined_data.extend(valid_signals)
    #self.combined_data_primary = valid_signals

    valid_signals = []
    for entry in combined_data:
      if (now - entry["time_final"]) < self.max_signal_age:
        valid_signals.append(entry)

    combined_data.clear()
    combined_data.extend(valid_signals)

  def update(self):
    self._scrub_combined_data(self.combined_data_primary, self.detection_data_primary)
    self._scrub_combined_data(self.combined_data_secondary, self.detection_data_secondary)
