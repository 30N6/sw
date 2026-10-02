import json
import numpy as np

class pluto_intercept_sw_config:
  def __init__(self, filename):
    self.filename = filename
    with open(filename, "r") as fd:
      self.config = json.load(fd)

    self._sanity_check()

    self.graphics     = self.config["graphics"]
    self.debug_log    = self.config["debug_log"]
    self.sim_enabled  = self.config["simulation"]["playback_enable"]
    self.dwell_data   = self.config["dwell"]

    #TODO: thresholds

  def _sanity_check(self):
    #TODO: config sanity check
    pass