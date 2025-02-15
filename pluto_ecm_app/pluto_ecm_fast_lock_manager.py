import pluto_ecm_logger
#import pluto_ecm_hw_interface
from pluto_ecm_hw_interface import hw_command
import time

class fast_lock_cal_state:
  def __init__(self, freq, fast_lock_profile_index):
    self.frequency                  = freq
    self.fast_lock_profile_index    = fast_lock_profile_index
    self.fast_lock_profile_valid    = False
    self.fast_lock_profile_updated  = False
    self.fast_lock_profile_data_rx  = []
    self.fast_lock_profile_data_tx  = []
    self.fast_lock_profile_time     = 0

  def __str__(self):
    return "[fast_lock_cal_state: {} : {} {} rx={} tx={}]".format(self.frequency, self.fast_lock_profile_index, self.fast_lock_profile_valid, self.fast_lock_profile_data_rx, self.fast_lock_profile_data_tx)
  def __repr__(self):
    return self.__str__()

class pluto_ecm_fast_lock_manager:
  def __init__(self, logger, sw_config, hw_interface):
    self.logger = logger
    self.hwi    = hw_interface
    self.hwcp   = hw_interface.hwcp

    self.fast_lock_cal_pending_rx       = []
    self.fast_lock_cal_pending_tx       = []
    self.fast_lock_cal_results_rx       = {}
    self.fast_lock_cal_results_tx       = {}

    self.fast_lock_cal_pending_freq     = []

    self.dwell_freqs                    = [d["freq"] for d in sw_config.config["dwell_config"]["dwell_freqs"]]
    self.fast_lock_recal_interval       = sw_config.config["fast_lock_config"]["recalibration_interval"]
    self.fast_lock_recal_pause          = sw_config.config["fast_lock_config"]["recalibration_pause"]
    self.fast_lock_last_cal_time        = None
    self.fast_lock_initial_cal_sent     = False
    self.fast_lock_initial_cal_done     = False
    self.current_fast_lock_profiles_rx  = {}
    self.current_fast_lock_profiles_tx  = {}

    self.fast_lock_load_pending         = []
    self.fast_lock_cal_state            = []

    for entry in sw_config.config["dwell_config"]["dwell_freqs"]:
      self.fast_lock_cal_state.append(fast_lock_cal_state(entry["freq"], entry["index"]))
      self.logger.log(self.logger.LL_INFO, "[pluto_ecm_fast_lock_manager] fast_lock_cal_state: added {}".format(self.fast_lock_cal_state[-1]))

    self.logger.log(self.logger.LL_INFO, "[pluto_ecm_fast_lock_manager] init done")

  def _send_fast_lock_cal_cmd(self, frequency):
    self.logger.log(self.logger.LL_INFO, "[pluto_ecm_fast_lock_manager] _send_fast_lock_cal_cmd: freq={}".format(frequency))

    cmd_rx = []
    cmd_rx.append(hw_command.gen_write_attr_rx_lo(self.hwcp.get_next_unique_key(), "frequency", str(int(frequency * 1e6))))
    cmd_rx.append(hw_command.gen_write_attr_rx_lo(self.hwcp.get_next_unique_key(), "fastlock_store", "0"))
    cmd_rx.append(hw_command.gen_read_attr_rx_lo(self.hwcp.get_next_unique_key(), "fastlock_save"))
    self.fast_lock_cal_pending_rx.append({"freq": frequency, "keys": [c["unique_key"] for c in cmd_rx]})

    cmd_tx = []
    cmd_tx.append(hw_command.gen_write_attr_tx_lo(self.hwcp.get_next_unique_key(), "frequency", str(int(frequency * 1e6))))
    cmd_tx.append(hw_command.gen_write_attr_tx_lo(self.hwcp.get_next_unique_key(), "fastlock_store", "0"))
    cmd_tx.append(hw_command.gen_read_attr_tx_lo(self.hwcp.get_next_unique_key(), "fastlock_save"))
    self.fast_lock_cal_pending_tx.append({"freq": frequency, "keys": [c["unique_key"] for c in cmd_tx]})

    for entry in cmd_rx:
      self.hwcp.send_command(entry, True)

    for entry in cmd_tx:
      self.hwcp.send_command(entry, True)

  def _send_fast_lock_profile_data(self, profile_index, profile_data_rx, profile_data_tx):
    modified_data_rx = "{} {}".format(profile_index, profile_data_rx.split(" ")[1])
    modified_data_tx = "{} {}".format(profile_index, profile_data_tx.split(" ")[1])
    cmd_rx = hw_command.gen_write_attr_rx_lo(self.hwcp.get_next_unique_key(), "fastlock_load", modified_data_rx)
    cmd_tx = hw_command.gen_write_attr_tx_lo(self.hwcp.get_next_unique_key(), "fastlock_load", modified_data_tx)
    key_rx = self.hwcp.send_command(cmd_rx, True)
    key_tx = self.hwcp.send_command(cmd_tx, True)
    self.fast_lock_load_pending.append(key_rx)
    self.fast_lock_load_pending.append(key_tx)
    return key_rx, key_tx

  def _send_fastlock_recall(self, value_rx, value_tx):
    cmd_rx = hw_command.gen_write_attr_rx_lo(self.hwcp.get_next_unique_key(), "fastlock_recall", value_rx)
    cmd_tx = hw_command.gen_write_attr_tx_lo(self.hwcp.get_next_unique_key(), "fastlock_recall", value_tx)
    key_rx = self.hwcp.send_command(cmd_rx, True)
    key_tx = self.hwcp.send_command(cmd_tx, True)
    self.fast_lock_load_pending.append(key_rx)
    self.fast_lock_load_pending.append(key_tx)
    return key_rx, key_tx

  def _try_send_fast_lock_profile(self, profile_index, profile_data_rx, profile_data_tx, force):
    #self.logger.log(self.logger.LL_DEBUG, "[pluto_ecm_fast_lock_manager] index={} force={} data_rx={} data_tx={}".format(profile_index, force, profile_data_rx, profile_data_tx))
    #self.logger.log(self.logger.LL_DEBUG, "[pluto_ecm_fast_lock_manager] current_fast_lock_profiles_rx={}".format(self.current_fast_lock_profiles_rx))
    #self.logger.log(self.logger.LL_DEBUG, "[pluto_ecm_fast_lock_manager] current_fast_lock_profiles_tx={}".format(self.current_fast_lock_profiles_tx))

    if ((profile_index in self.current_fast_lock_profiles_rx) and (self.current_fast_lock_profiles_rx[profile_index] == profile_data_rx) and
        (profile_index in self.current_fast_lock_profiles_tx) and (self.current_fast_lock_profiles_tx[profile_index] == profile_data_tx) and
        (not force)):
      self.logger.log(self.logger.LL_INFO, "[pluto_ecm_fast_lock_manager] skipping fast lock profile, already loaded: index={}".format(profile_index))
      return False

    self.current_fast_lock_profiles_rx[profile_index] = profile_data_rx
    self.current_fast_lock_profiles_tx[profile_index] = profile_data_tx
    key_rx, key_tx = self._send_fast_lock_profile_data(profile_index, profile_data_rx, profile_data_tx)
    self.logger.log(self.logger.LL_INFO, "[pluto_ecm_fast_lock_manager] sending fast lock profile: index={} uk_rx={} uk_tx={}".format(profile_index, key_rx, key_tx))
    return True

  def _set_fast_lock_recall(self):
    cmd_rx = hw_command.gen_write_attr_dbg(self.hwcp.get_next_unique_key(), "adi,rx-fastlock-pincontrol-enable", "1")
    cmd_tx = hw_command.gen_write_attr_dbg(self.hwcp.get_next_unique_key(), "adi,tx-fastlock-pincontrol-enable", "1")
    self.hwcp.send_command(cmd_rx, False)
    self.hwcp.send_command(cmd_tx, False)

    key_rx, key_tx = self._send_fastlock_recall("0", "0")
    self.logger.log(self.logger.LL_INFO, "[pluto_ecm_fast_lock_manager] fastlock_recall=0 - uk_rx={} uk_tx={}".format(key_rx, key_tx))

  def _get_oldest_cal(self):
    oldest_entry = self.fast_lock_cal_state[0]
    for entry in self.fast_lock_cal_state:
      if (not entry.fast_lock_profile_valid) or (entry.fast_lock_profile_time < oldest_entry.fast_lock_profile_time):
        oldest_entry = entry
    return oldest_entry

  def _get_cal_by_freq(self, freq):
    for entry in self.fast_lock_cal_state:
      if entry.frequency == freq:
        return entry
    raise RuntimeError("failed to find cal frequency")

  def _update_fast_lock_cal(self):
    now = time.time()

    if not self.fast_lock_initial_cal_sent:
      for freq in self.dwell_freqs:
        self.fast_lock_cal_pending_freq.append(freq)
        self.logger.log(self.logger.LL_INFO, "[pluto_ecm_fast_lock_manager] requesting initial fast lock cal for freq={}".format(freq))
        self._send_fast_lock_cal_cmd(freq)

      self.fast_lock_initial_cal_sent = True
      self.logger.log(self.logger.LL_INFO, "[pluto_ecm_fast_lock_manager] initial cal sent")

    if len(self.fast_lock_cal_pending_freq) == 0:
      if (now - self.fast_lock_last_cal_time) < self.fast_lock_recal_pause:
        return

      oldest_cal = self._get_oldest_cal()
      if oldest_cal.fast_lock_profile_valid and ((now - oldest_cal.fast_lock_profile_time) < self.fast_lock_recal_interval):
        return

      self.fast_lock_cal_pending_freq.append(oldest_cal.frequency)
      self.logger.log(self.logger.LL_INFO, "[pluto_ecm_fast_lock_manager] requesting fast lock cal for freq={}: prior_valid={} prior_age={}".format(
        oldest_cal.frequency, oldest_cal.fast_lock_profile_valid, (now - oldest_cal.fast_lock_profile_time)))
      self._send_fast_lock_cal_cmd(oldest_cal.frequency)

    else:
      if (self.fast_lock_cal_pending_freq[0] not in self.fast_lock_cal_results_rx) or (self.fast_lock_cal_pending_freq[0] not in self.fast_lock_cal_results_tx):
        return

      freq = self.fast_lock_cal_pending_freq.pop(0)
      results_rx = self.fast_lock_cal_results_rx.pop(freq)
      results_tx = self.fast_lock_cal_results_tx.pop(freq)

      cal_state = self._get_cal_by_freq(freq)
      cal_state.fast_lock_profile_valid   = True
      cal_state.fast_lock_profile_updated = True
      cal_state.fast_lock_profile_time    = now
      cal_state.fast_lock_profile_data_rx = results_rx
      cal_state.fast_lock_profile_data_tx = results_tx
      self.fast_lock_last_cal_time        = now
      self.logger.log(self.logger.LL_INFO, "[pluto_ecm_fast_lock_manager] received fast lock cal data for freq={}: rx={} tx={}".format(freq, cal_state.fast_lock_profile_data_rx, cal_state.fast_lock_profile_data_tx))

      if not self.fast_lock_initial_cal_done:
        if all([d.fast_lock_profile_valid for d in self.fast_lock_cal_state]):
          self.fast_lock_initial_cal_done = True

  def _check_pending_fast_lock_profiles(self):
    keys_found = []
    for k in self.fast_lock_load_pending:
      if self.hwcp.try_get_result(k) is not None:
        keys_found.append(k)
    for k in keys_found:
      self.fast_lock_load_pending.remove(k)
      self.logger.log(self.logger.LL_INFO, "[pluto_ecm_fast_lock_manager] pending fast lock profile acknowledged -- uk={}".format(k))
    return len(keys_found)

  def _check_pending_results(self):
    if len(self.fast_lock_cal_pending_rx) > 0:
      cmd_result = self.hwcp.try_get_result(self.fast_lock_cal_pending_rx[0]["keys"][0])
      if cmd_result is not None:
        finished_key = self.fast_lock_cal_pending_rx[0]["keys"].pop(0)
        assert (cmd_result["unique_key"] == finished_key)

        self.logger.log(self.logger.LL_INFO, "[pluto_ecm_fast_lock_manager] fast_lock_cal_pending_rx received -- uk={}".format(finished_key))

        if len(self.fast_lock_cal_pending_rx[0]["keys"]) == 0:
          freq = self.fast_lock_cal_pending_rx[0]["freq"]
          self.fast_lock_cal_pending_rx.pop(0)
          self.fast_lock_cal_results_rx[freq] = cmd_result["data"]

    if len(self.fast_lock_cal_pending_tx) > 0:
      cmd_result = self.hwcp.try_get_result(self.fast_lock_cal_pending_tx[0]["keys"][0])
      if cmd_result is not None:
        finished_key = self.fast_lock_cal_pending_tx[0]["keys"].pop(0)
        assert (cmd_result["unique_key"] == finished_key)

        self.logger.log(self.logger.LL_INFO, "[pluto_ecm_fast_lock_manager] fast_lock_cal_pending_tx received -- uk={}".format(finished_key))

        if len(self.fast_lock_cal_pending_tx[0]["keys"]) == 0:
          freq = self.fast_lock_cal_pending_tx[0]["freq"]
          self.fast_lock_cal_pending_tx.pop(0)
          self.fast_lock_cal_results_tx[freq] = cmd_result["data"]

  def on_active_next_dwells(self):
    force_fast_lock_update = False
    for cal_entry in self.fast_lock_cal_state:
      force_fast_lock_update |= cal_entry.fast_lock_profile_updated
      cal_entry.fast_lock_profile_updated = False

    fast_lock_profile_sent = False
    for cal_entry in self.fast_lock_cal_state:
      fast_lock_profile_sent |= self._try_send_fast_lock_profile(cal_entry.fast_lock_profile_index, cal_entry.fast_lock_profile_data_rx, cal_entry.fast_lock_profile_data_tx, force_fast_lock_update)

    if fast_lock_profile_sent:
      self._set_fast_lock_recall()

  def update(self):
    self._check_pending_fast_lock_profiles()
    self._check_pending_results()
    self._update_fast_lock_cal()
