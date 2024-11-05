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
  def __init__(self, logger, sw_config, hw_interface):
    self.logger                     = logger
    self.hw_interface               = hw_interface
    self.state                      = "IDLE"
    self.fast_lock_cal_pending      = None
    self.fast_lock_recal_interval   = sw_config.fast_lock_recal_interval
    self.fast_lock_recal_pause      = sw_config.fast_lock_recal_pause
    self.fast_lock_initial_cal_done = False
    self.fast_lock_last_cal_time    = None

    print(sw_config)

    self.scan_dwells = {}
    for freq in sw_config.scan_dwells:
      self.scan_dwells[freq] = dwell_data(freq, sw_config.scan_dwells[freq])

    for freq in self.scan_dwells:
      self.logger.log(self.logger.LL_DEBUG, "[sequencer] scan_dwells[{}]=[{}]".format(freq, self.scan_dwells[freq]))
    self.logger.log(self.logger.LL_INFO, "[sequencer] init done")

  def get_oldest_cal_freq(self):
    oldest_freq = list(self.scan_dwells.keys())[0]
    oldest_time = self.scan_dwells[oldest_freq].fast_lock_profile_time
    for freq in self.scan_dwells:
      dwell = self.scan_dwells[freq]
      if (not dwell.fast_lock_profile_valid) or (dwell.fast_lock_profile_time < oldest_time):
        oldest_time = dwell.fast_lock_profile_time
        oldest_freq = freq
    return oldest_freq

  def update_fast_lock_cal(self):
    now = time.time()
    if self.fast_lock_cal_pending is None:
      if self.fast_lock_initial_cal_done and ((now - self.fast_lock_last_cal_time) < self.fast_lock_recal_pause):
        return

      freq = self.get_oldest_cal_freq()
      dwell = self.scan_dwells[freq]
      if dwell.fast_lock_profile_valid and ((now - dwell.fast_lock_profile_time) < self.fast_lock_recal_interval):
        return

      self.fast_lock_cal_pending = freq
      self.logger.log(self.logger.LL_INFO, "[sequencer] requesting fast lock cal for freq={}: prior_valid={} prior_age={}".format(
        freq, dwell.fast_lock_profile_valid, (now - dwell.fast_lock_profile_time)))
      self.hw_interface.send_fast_lock_cal_cmd(freq)

    else:
      cal_results = self.hw_interface.check_fast_lock_cal_results()
      if cal_results is not None:
        assert (cal_results["freq"] == self.fast_lock_cal_pending)
        dwell = self.scan_dwells[cal_results["freq"]]
        dwell.fast_lock_profile_valid = True
        dwell.fast_lock_profile_time  = now
        dwell.fast_lock_profile_data  = cal_results["data"]
        self.fast_lock_cal_pending    = None
        self.fast_lock_last_cal_time  = now
        self.logger.log(self.logger.LL_INFO, "[sequencer] received fast lock cal data for freq={}: {}".format(cal_results["freq"], dwell.fast_lock_profile_data))

        if not self.fast_lock_initial_cal_done:
          prof_valid = [d.fast_lock_profile_valid for d in self.scan_dwells.values()]
          if all(prof_valid):
            self.fast_lock_initial_cal_done = True
            self.logger.log(self.logger.LL_INFO, "[sequencer] initial cal complete")

  def update(self):
    self.update_fast_lock_cal()
    pass