import time
import random
import pluto_esm_hw_dwell
import pluto_esm_hw_dwell_reporter
import pluto_esm_hw_interface
import pluto_esm_hw_pkg

class dwell_data:
  def __init__(self, frequency, dwell_time):
    self.frequency                  = frequency
    self.dwell_time                 = dwell_time
    self.fast_lock_profile_valid    = False
    self.fast_lock_profile_updated  = False
    self.fast_lock_profile_data     = []
    self.fast_lock_profile_time     = 0

    self.hw_dwell_valid             = False
    self.hw_dwell_entry             = pluto_esm_hw_dwell.esm_message_dwell_entry.default_dwell()

    self.first_dwell                = False
    self.last_dwell                 = False

  def __str__(self):
    return "dwell_data: {} {} {} {}".format(self.frequency, self.dwell_time, self.fast_lock_profile_valid, self.fast_lock_profile_data)
  def __repr__(self):
    return self.__str__()

class pluto_esm_sequencer:
  MAX_ACTIVE_SCAN_DWELLS    = 6
  MAX_ACTIVE_REVISIT_DWELLS = 2

  def __init__(self, logger, sw_config, hw_interface):
    self.logger                         = logger
    self.hw_interface                   = hw_interface
    self.dwell_ctrl_interface           = pluto_esm_hw_dwell.esm_dwell_controller(hw_interface.hw_cfg)
    self.dwell_reporter                 = pluto_esm_hw_dwell_reporter.pluto_esm_hw_dwell_reporter(logger)

    self.state                          = "IDLE"

    self.fast_lock_recal_interval       = sw_config.fast_lock_recal_interval
    self.fast_lock_recal_pause          = sw_config.fast_lock_recal_pause
    self.fast_lock_cal_pending          = []
    self.fast_lock_last_cal_time        = None
    self.fast_lock_initial_cal_sent     = False
    self.fast_lock_initial_cal_done     = False

    self.initial_hw_scan_dwells_sent    = False
    self.initial_hw_scan_dwells_loaded  = False
    self.hw_dwell_entry_pending         = []
    self.hw_dwell_program_pending       = []
    self.fast_lock_load_pending         = []

    self.current_fast_lock_profiles     = {}

    self.dwell_state                    = "IDLE"
    self.dwell_active                   = []  #TODO: rename
    self.dwell_active_first             = []
    self.dwell_active_last              = []
    self.dwell_history                  = {}

    self.dwells_to_render               = []

    self.scan_sequence                  = []
    self.randomize_scan_order           = sw_config.randomize_scan_order

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

    #TODO: break out into two functions

    if not self.fast_lock_initial_cal_sent:
      for freq in self.scan_dwells:
        dwell = self.scan_dwells[freq]
        self.fast_lock_cal_pending.append(freq)
        self.logger.log(self.logger.LL_INFO, "[sequencer] requesting initial fast lock cal for freq={}".format(freq))
        self.hw_interface.send_fast_lock_cal_cmd(freq)
        self.fast_lock_initial_cal_sent = True
        self.logger.log(self.logger.LL_INFO, "[sequencer] initial cal sent")

    if len(self.fast_lock_cal_pending) == 0:
      if (now - self.fast_lock_last_cal_time) < self.fast_lock_recal_pause:
        return

      freq = self.get_oldest_cal_freq()
      dwell = self.scan_dwells[freq]
      if dwell.fast_lock_profile_valid and ((now - dwell.fast_lock_profile_time) < self.fast_lock_recal_interval):
        return

      self.fast_lock_cal_pending.append(freq)
      self.logger.log(self.logger.LL_INFO, "[sequencer] requesting fast lock cal for freq={}: prior_valid={} prior_age={}".format(
        freq, dwell.fast_lock_profile_valid, (now - dwell.fast_lock_profile_time)))
      self.hw_interface.send_fast_lock_cal_cmd(freq)

    else:
      cal_results = self.hw_interface.check_fast_lock_cal_results()
      if cal_results is not None:
        assert (cal_results["freq"] == self.fast_lock_cal_pending[0])
        dwell = self.scan_dwells[cal_results["freq"]]
        dwell.fast_lock_profile_valid   = True
        dwell.fast_lock_profile_updated = True
        dwell.fast_lock_profile_time    = now
        dwell.fast_lock_profile_data    = cal_results["data"]
        self.fast_lock_last_cal_time    = now
        self.fast_lock_cal_pending.pop(0)
        self.logger.log(self.logger.LL_INFO, "[sequencer] received fast lock cal data for freq={}: {}".format(cal_results["freq"], dwell.fast_lock_profile_data))

        if not self.fast_lock_initial_cal_done:
          if all([d.fast_lock_profile_valid for d in self.scan_dwells.values()]):
            self.fast_lock_initial_cal_done = True

  def send_initial_hw_dwells(self):
    freq_list = list(self.scan_dwells.keys())
    for i in range(len(freq_list)):
      freq = freq_list[i]
      dwell = self.scan_dwells[freq]
      fast_lock_profile = i % self.MAX_ACTIVE_SCAN_DWELLS

      dwell.hw_dwell_entry = pluto_esm_hw_dwell.esm_message_dwell_entry.default_scan_dwell(i, i, freq, dwell.dwell_time, fast_lock_profile)
      dwell.hw_entry_valid = True

      dwell_key = self.dwell_ctrl_interface.send_dwell_entry(dwell.hw_dwell_entry)
      self.hw_dwell_entry_pending.append(dwell_key)

      self.logger.log(self.logger.LL_INFO, "[sequencer] sending initial hw scan dwell for freq={}: dwell_time={} fast_lock_profile={} -- uk={}".format(
        freq, dwell.dwell_time, fast_lock_profile, dwell_key))

  def send_hw_dwell_program(self, dwell_program):
    key = self.dwell_ctrl_interface.send_dwell_program(dwell_program)
    self.hw_dwell_program_pending.append(key)
    self.logger.log(self.logger.LL_INFO, "[sequencer] sending dwell program: uk={}".format(key))

  def send_fast_lock_profile(self, profile_index, dwell_data, force):
    assert (dwell_data.fast_lock_profile_valid)
    if ((profile_index in self.current_fast_lock_profiles) and (self.current_fast_lock_profiles[profile_index] == dwell_data.fast_lock_profile_data) and (not force)):
      self.logger.log(self.logger.LL_INFO, "[sequencer] skipping fast lock profile, already loaded: index={}".format(profile_index))
      return False

    self.current_fast_lock_profiles[profile_index] = dwell_data.fast_lock_profile_data
    key = self.hw_interface.send_fast_lock_profile(profile_index, dwell_data.fast_lock_profile_data)
    self.fast_lock_load_pending.append(key)
    self.logger.log(self.logger.LL_INFO, "[sequencer] sending fast lock profile: index={} uk={}".format(profile_index, key))
    return True

  def set_fast_lock_recall(self):
    #TODO: remove
    cmd = pluto_esm_hw_interface.hw_command.gen_write_attr_dbg(self.hw_interface.hwcp.get_next_unique_key(), "adi,rx-fastlock-pincontrol-enable", "1")
    self.hw_interface.hwcp.send_command(cmd, False)

    key = self.hw_interface.send_fastlock_recall("0")
    self.fast_lock_load_pending.append(key)
    self.logger.log(self.logger.LL_INFO, "[sequencer] fastlock_recall=0")
    #self.logger.log(

  #TODO: use a generic function to reduce code duplication
  def check_pending_hw_dwells(self):
    keys_found = []
    for k in self.hw_dwell_entry_pending:
      if self.hw_interface.hwcp.try_get_result(k) is not None:
        keys_found.append(k)
    for k in keys_found:
      self.hw_dwell_entry_pending.remove(k)
      self.logger.log(self.logger.LL_INFO, "[sequencer] pending hw dwell entry acknowledged -- uk={}".format(k))
    return len(keys_found)

  def check_pending_hw_dwell_programs(self):
    keys_found = []
    for k in self.hw_dwell_program_pending:
      if self.hw_interface.hwcp.try_get_result(k) is not None:
        keys_found.append(k)
    for k in keys_found:
      self.hw_dwell_program_pending.remove(k)
      self.logger.log(self.logger.LL_INFO, "[sequencer] pending hw dwell program acknowledged -- uk={}".format(k))
    return len(keys_found)

  def check_pending_fast_lock_profiles(self):
    keys_found = []
    for k in self.fast_lock_load_pending:
      if self.hw_interface.hwcp.try_get_result(k) is not None:
        keys_found.append(k)
    for k in keys_found:
      self.fast_lock_load_pending.remove(k)
      self.logger.log(self.logger.LL_INFO, "[sequencer] pending fast lock profile acknowledged -- uk={}".format(k))
    return len(keys_found)

  def update_hw_dwells(self):
    self.check_pending_hw_dwells()

    if (self.state == "LOAD_HW_SCAN_DWELLS" and (not self.initial_hw_scan_dwells_sent)):
      self.send_initial_hw_dwells()
      self.initial_hw_scan_dwells_sent = True

    if self.initial_hw_scan_dwells_sent and (not self.initial_hw_scan_dwells_loaded):
      if len(self.hw_dwell_entry_pending) == 0:
        self.initial_hw_scan_dwells_loaded = True

    #TODO: load revisit dwells as necessary

  def compute_next_dwell_program(self):
    assert (len(self.dwell_active) > 0)
    dwell_instructions  = []
    next_instruction_index = 0
    #TODO: randomize dwell order
    for entry in self.dwell_active:
      #TODO: don't skip PLL checks
      dwell = entry["dwell"]
      next_instruction_index += 1
      dwell_instructions.append(pluto_esm_hw_dwell.esm_dwell_instruction(1, 0, 0, 1, 1, 1, 0, dwell.hw_dwell_entry.entry_index, next_instruction_index))
    for _ in range(pluto_esm_hw_pkg.ESM_NUM_DWELL_INSTRUCTIONS - len(dwell_instructions)):
      dwell_instructions.append(pluto_esm_hw_dwell.esm_dwell_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0))

    return pluto_esm_hw_dwell.esm_message_dwell_program(1, 0, 0, 0, dwell_instructions)

  def process_dwell_reports(self):
    while len(self.hw_interface.hwdr.output_data_dwell) > 0:
      packed_report = self.hw_interface.hwdr.output_data_dwell.pop(0)
      combined_report = self.dwell_reporter.process_message(packed_report)

      expected_entry = self.dwell_active[0]
      expected_dwell = expected_entry["dwell"]

      if combined_report is not None:
        assert (combined_report["frequency"] == int(round(expected_dwell.frequency)))
        self.logger.log(self.logger.LL_INFO, "[sequencer] process_dwell_reports: combined report received for frequency={}".format(expected_dwell.frequency))

        #data for rendering the dwell indicator
        if expected_entry["first"]:
          self.dwell_history = {}
        self.dwell_history[expected_dwell.frequency] = time.time()

        #data for rendering the spectrogram
        self.dwells_to_render.append({"dwell_data": expected_dwell, "dwell_report": combined_report, "first_in_sequence": expected_entry["first"], "last_in_sequence": expected_entry["last"]})
        self.dwell_active.pop(0)
      else:
        self.logger.log(self.logger.LL_INFO, "[sequencer] process_dwell_reports: partial report")

  def activate_next_dwells(self):
    assert (len(self.dwell_active) == 0)

    force_fast_lock_update = False
    while (len(self.scan_sequence) > 0) and (len(self.dwell_active) < self.MAX_ACTIVE_SCAN_DWELLS):
      current_entry = self.scan_sequence.pop(0)
      force_fast_lock_update |= current_entry["dwell"].fast_lock_profile_updated
      current_entry["dwell"].fast_lock_profile_updated = False
      self.dwell_active.append(current_entry)

    fast_lock_profile_sent = False
    for current_entry in self.dwell_active:
      current_dwell = current_entry["dwell"]
      assert (current_dwell.hw_entry_valid)
      fast_lock_profile = current_dwell.hw_dwell_entry.fast_lock_profile
      fast_lock_profile_sent |= self.send_fast_lock_profile(fast_lock_profile, current_dwell, force_fast_lock_update)
      self.logger.log(self.logger.LL_INFO, "[sequencer] activate_next_dwells: preparing to start new dwell: freq {}, fast lock profile {} -- {} dwells remaining in sequence".format(current_dwell.frequency, fast_lock_profile, len(self.scan_sequence)))

    if fast_lock_profile_sent:
      self.set_fast_lock_recall()

  def prepare_scan_sequence(self):
    assert (len(self.scan_sequence) == 0)
    assert (len(self.dwell_active) == 0)

    dwell_sequence = list(self.scan_dwells.values())
    if self.randomize_scan_order:
      random.shuffle(dwell_sequence) #try to avoid aliasing with periodic signals

    self.scan_sequence = []
    for i in range(len(dwell_sequence)):
      self.scan_sequence.append({"dwell": dwell_sequence[i], "first": (i == 0), "last": (i == (len(dwell_sequence) - 1))})

  def update_scan_dwells(self):
    if self.state != "ACTIVE":
      self.dwell_state = "IDLE"
      return

    self.check_pending_fast_lock_profiles()
    self.check_pending_hw_dwell_programs()

    if self.dwell_state == "IDLE":
      #TODO: check enable
      self.dwell_state = "LOAD_SEQUENCE"

    if self.dwell_state == "LOAD_SEQUENCE":
      self.prepare_scan_sequence()
      self.dwell_state = "LOAD_DWELLS"

    if self.dwell_state == "LOAD_DWELLS":
      self.activate_next_dwells()
      self.dwell_state = "LOAD_PROFILES"

      #TODO: figure out if dwell entries need to be updated
      #TODO: send dwell program immediately, or wait for ack?

    if self.dwell_state == "LOAD_PROFILES":
      assert (len(self.dwell_active) > 0)
      if len(self.fast_lock_load_pending) == 0:
        self.dwell_state = "SEND_PROGRAM"
        dwell_program = self.compute_next_dwell_program()
        self.send_hw_dwell_program(dwell_program)
        self.logger.log(self.logger.LL_INFO, "[sequencer] update_scan_dwells [LOAD_PROFILES]: profiles loaded, sending dwell program")

    if self.dwell_state == "SEND_PROGRAM":
      if len(self.hw_dwell_program_pending) == 0:
        self.logger.log(self.logger.LL_INFO, "[sequencer] update_scan_dwells [SEND_PROGRAM]: dwell program sent, going active")
        self.dwell_state = "HW_ACTIVE"

    if self.dwell_state == "HW_ACTIVE":
      self.process_dwell_reports()
      if (len(self.dwell_active) == 0):
        self.logger.log(self.logger.LL_INFO, "[sequencer] update_scan_dwells [HW_ACTIVE]: dwells completed")
        self.dwell_state = "DWELLS_COMPLETE"

    if self.dwell_state == "DWELLS_COMPLETE":
      if len(self.scan_sequence) == 0:
        self.dwell_state = "IDLE"
      else:
        self.dwell_state = "LOAD_DWELLS"
      #TODO: update waterfall?
      #self.hw_interface.hw_cfg.send_reset()

  def update(self):
    if self.state == "IDLE":
      self.state = "INITIAL_CAL"
    elif self.state == "INITIAL_CAL":
      if self.fast_lock_initial_cal_done:
        self.state = "LOAD_HW_SCAN_DWELLS"
    elif self.state == "LOAD_HW_SCAN_DWELLS":
      if self.initial_hw_scan_dwells_loaded:
        self.state = "ACTIVE"
    elif self.state == "ACTIVE":
      pass

    self.update_fast_lock_cal()
    self.update_hw_dwells()
    self.update_scan_dwells()