from pluto_esm_hw_pkg import *
import time
import numpy as np

class pluto_esm_dwell_processor:
  def __init__(self, logger):
    self.logger = logger

    self.channel_data_history = {}
    self.channel_data_summary = {}
    self.threshold_data       = {}
    self.detection_data       = {}

    self.max_dwell_age        = 300 #TODO: config?
    self.max_signal_age       = 30
    self.threshold_factor     = 4 #TODO: config -- TODO: different by frequency?
    self.threshold_min        = 0.1 #TODO: config
    self.num_threshold_dwells = 5 #TODO: config?

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

      #self.logger.log(self.logger.LL_INFO, "[dwell_processor] freq={} summary: mean={} accum={} -- threshold={}/{}".format(freq, new_entry["accum_normalized"], self.channel_data_summary[freq]["accum_mean"],
      #  self.threshold_data[freq]["threshold_0_data"], self.threshold_data[freq]["threshold_1_data"]))

  def _update_threshold(self, freq):
    if freq not in self.threshold_data:
      self.threshold_data[freq] = {"threshold_0_data": 0, "threshold_1_data": 0, "threshold_factor": 0, "threshold_valid": False}

    if (not self.threshold_data[freq]["threshold_valid"]) and (len(self.channel_data_history[freq]) >= 5):
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

    now = time.time()

    if detection_level > 0:
      if freq not in self.detection_data:
        self.detection_data[freq] = {"power": 0, "num_dwells": 0, "detection_level": 0, "time_initial": now, "time_final": 0}
        self.logger.log(self.logger.LL_INFO, "[dwell_processor] new signal: freq={:.2f} detection_level={} power={:.3f} -- thresholds={:.3f}/{:.3f}".format(freq, detection_level, dwell_entry["accum_normalized"],
          self.threshold_data[freq]["threshold_0_data"], self.threshold_data[freq]["threshold_1_data"]))

      self.detection_data[freq]["power_threshold"]  = np.minimum(self.threshold_data[freq]["threshold_0_data"], self.threshold_data[freq]["threshold_1_data"])
      self.detection_data[freq]["power_mean"]       = dwell_entry["accum_normalized"]
      self.detection_data[freq]["power_max"]        = dwell_entry["max"]
      self.detection_data[freq]["num_dwells"]       += 1
      self.detection_data[freq]["detection_level"]  = detection_level
      self.detection_data[freq]["time_final"]       = now

    elif freq in self.detection_data:
      if (now - self.detection_data[freq]["time_final"]) > self.max_signal_age:
        self.detection_data.pop(freq, None)
        self.logger.log(self.logger.LL_INFO, "[dwell_processor] stale signal removed: freq={}".format(freq))

  def _scrub_history(self):
    now = time.time()

  def update(self):
    self._scrub_history()
