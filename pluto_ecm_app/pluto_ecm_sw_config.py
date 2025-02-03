import json
import numpy as np

class pluto_ecm_sw_config:
  def __init__(self, filename):
    fd = open(filename, "r")
    self.config = json.load(fd)
    fd.close()

    self._sanity_check()

    self.graphics    = self.config["graphics"]
    self.debug_log   = self.config["debug_log"]
    self.sim_enabled = self.config["simulation"]["playback_enable"]

  def _sanity_check(self):
    for entry in self.config["dwell_config"]["exclude_freqs"]:
      assert (entry["freq_range"][0] <= entry["freq_range"][1])

    dwell_index = 0
    for entry in self.config["dwell_config"]["dwell_entries"]:
      assert (entry["index"] == dwell_index)
      assert (entry["dwell_total_time_max"] >= entry["dwell_measurement_time"])
      dwell_index += 1

    for d in self.config["dwell_config"]["dwell_pattern"]:
      assert (d < dwell_index)

    for entry in self.config["tx_config"]["signals"]:
      assert (entry["freq_range"][0]  <= entry["freq_range"][1])
      assert ((entry["trigger_duration"][0] <= entry["trigger_duration"][1]) or (entry["trigger_duration"][1] == -1))
