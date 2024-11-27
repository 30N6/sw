import json
import numpy as np

class pluto_esm_sw_config:
  def __init__(self, filename):
    fd = open(filename, "r")
    self.config = json.load(fd)
    fd.close()

    self.scan_dwells = self._compute_scan_dwells(self.config)
    self.randomize_scan_order = self.config["scan_config"]["randomize_scan_order"]
    self.min_freq = min(list(self.scan_dwells.keys())) - self.config["dwell_config"]["freq_step"] / 2
    self.max_freq = max(list(self.scan_dwells.keys())) + self.config["dwell_config"]["freq_step"] / 2
    self.fast_lock_recal_interval = self.config["fast_lock_config"]["recalibration_interval"]
    self.fast_lock_recal_pause = self.config["fast_lock_config"]["recalibration_pause"]

    self.sim_enabled = self.config["sim_mode"]["enable"]
    if self.sim_enabled:
      self.sim_filename = self.config["sim_mode"]["filename"]

    self.enable_recording = self.config["enable_recording"]

    #TODO: assertions for emitter entries - min/max of ranges, etc.

  def _compute_scan_dwells(self, config):
    max_freq = 0
    min_freq = 99999
    scan_config = config["scan_config"]
    for entry in scan_config["include_freqs"]:
      assert (entry["freq_range"][0] <= entry["freq_range"][1])
      max_freq = max(max_freq, entry["freq_range"][0], entry["freq_range"][1])
      min_freq = min(min_freq, entry["freq_range"][0], entry["freq_range"][1])

    for entry in scan_config["exclude_freqs"]:
      assert (entry["freq_range"][0] <= entry["freq_range"][1])

    channel_step = config["dwell_config"]["channel_step"]
    freq_step = config["dwell_config"]["freq_step"]
    assert (freq_step % channel_step < 1e-12)
    dwell_candidates = np.arange(config["dwell_config"]["freq_start"], max_freq + freq_step, freq_step)

    dwell_by_freq = {}
    for dwell_freq in dwell_candidates:
      dwell_channels = np.arange(dwell_freq - freq_step/2, dwell_freq + freq_step/2 + channel_step, channel_step)
      dwell_time = np.zeros(dwell_channels.size)
      for i in range(dwell_channels.size):
        chan_freq = dwell_channels[i]
        for entry in scan_config["include_freqs"]:
          if (chan_freq >= entry["freq_range"][0]) and (chan_freq < entry["freq_range"][1]):
            dwell_time[i] = max(dwell_time[i], entry["dwell_time"])
        for entry in scan_config["exclude_freqs"]:
          if (chan_freq >= entry["freq_range"][0]) and (chan_freq < entry["freq_range"][1]):
            dwell_time[i] = 0

      max_dwell_time = np.max(dwell_time)
      if max_dwell_time > 0:
        dwell_by_freq[dwell_freq] = max_dwell_time

    return dwell_by_freq
