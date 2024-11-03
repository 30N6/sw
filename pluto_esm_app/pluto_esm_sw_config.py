import json
import numpy as np

class pluto_esm_sw_config:
  def __init__(self, filename):
    fd = open(filename, "r")
    self.config = json.load(fd)
    fd.close()

    self.scan_dwells = self.compute_scan_dwells(self.config["scan_config"])

  def compute_scan_dwells(self, scan_config):
    max_freq = 0
    for entry in scan_config["include_freqs"]:
      max_freq = max(max_freq, entry["freq_range"][0], entry["freq_range"][1])

    dwell_time_bins = get_dwell_time_bins(scan_config, max_freq)

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

    pass