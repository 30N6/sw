import time
import numpy as np

class pluto_esm_dwell_processor:
  def __init__(self, logger):
    self.logger = logger

    self.dwell_history_accum = []
    self.max_dwell_age = 60 #TODO: config?

  def submit_dwell_data(self, combined_dwell_data):
    now = time.time()

  def _scrub_history(self):
    now = time.time()

  def update(self):
    self._scrub_history()
