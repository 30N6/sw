import time

class dwell_data:
  def __init__(self, frequency, dwell_time):
    self.frequency                = frequency
    self.dwell_time               = dwell_time
    self.fast_lock_profile_valid  = False
    self.fast_lock_profile_data   = []
    self.fast_lock_profile_time   = 0

  def __str__(self):
    return "dwell_data: {} {} {} {}".format(self.frequency, self.dwell_time, self.fast_lock_profile_valid, self.fast_lock_profile_data)
  def __repr__(self):
    return self.__str__()

class pluto_esm_sequencer:

  def __init__(self, scan_dwells, logger):
    #TODO: logging

    self.state = "IDLE"

    self.scan_dwells = {}
    for freq in scan_dwells:
      self.scan_dwells[freq] = dwell_data(freq, scan_dwells[freq])

    print(self.scan_dwells)

  def update(self):
    pass