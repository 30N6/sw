import json
import numpy as np

class pluto_esm_sw_config:
  def __init__(self, filename):
    fd = open(filename, "r")
    self.config = json.load(fd)
    fd.close()

    self.scan_dwells = self.compute_scan_dwells(self.config)
    self.max_freq = max(list(self.scan_dwells.keys())) + self.config["dwell_constraints"]["freq_step"] / 2
    self.fast_lock_recal_interval = self.config["fast_lock_config"]["recalibration_interval"]
    self.fast_lock_recal_pause = self.config["fast_lock_config"]["recalibration_pause"]

  def compute_scan_dwells(self, config):
    max_freq = 0
    scan_config = config["scan_config"]
    for entry in scan_config["include_freqs"]:
      max_freq = max(max_freq, entry["freq_range"][0], entry["freq_range"][1])

    dwell_time_bins = self.get_dwell_time_bins(scan_config, max_freq)
    dwell_by_freq = self.get_dwells_from_bins(dwell_time_bins, config["dwell_constraints"])
    return dwell_by_freq

  def get_dwells_from_bins(self, bins, dwell_constraints):
    dwells = {}

    for freq in range(len(bins)):
      if bins[freq] == 0:
        continue
      nearest_dwell_freq = int(np.round((freq - dwell_constraints["freq_start"]) / dwell_constraints["freq_step"]) * dwell_constraints["freq_step"] + dwell_constraints["freq_start"])
      if nearest_dwell_freq not in dwells:
        dwells[nearest_dwell_freq] = bins[freq]
      else:
        dwells[nearest_dwell_freq] = max(dwells[nearest_dwell_freq], bins[freq])

    return dwells

  def get_dwell_time_bins(self, scan_config, max_freq):
    dwell_time_bins = np.zeros(max_freq + 1)
    for entry in scan_config["include_freqs"]:
      assert (entry["freq_range"][0] <= entry["freq_range"][1])
      i_start = entry["freq_range"][0]
      i_end   = entry["freq_range"][1] + 1
      current_dwell_time = np.ones(i_end - i_start) * entry["dwell_time"]
      dwell_time_bins[i_start:i_end] = np.maximum(dwell_time_bins[i_start:i_end], current_dwell_time)

    for entry in scan_config["exclude_freqs"]:
      assert (entry["freq_range"][0] <= entry["freq_range"][1])
      i_start = entry["freq_range"][0]
      i_end   = entry["freq_range"][1] + 1
      dwell_time_bins[i_start:i_end] = 0

    return dwell_time_bins
