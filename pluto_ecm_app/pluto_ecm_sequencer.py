import time
import random
import json
from pluto_ecm_hw_pkg import *
import pluto_ecm_hw_stats
import pluto_ecm_hw_interface
import pluto_ecm_hw_dwell
import pluto_ecm_hw_dwell_reporter
import pluto_ecm_hw_drfm_reporter
import pluto_ecm_dwell_stats_buffer
import pluto_ecm_ecm_controller

class dwell_data:
  def __init__(self, dwell_index, next_dwell_index, is_first, is_last, freq_entry):
    self.dwell_index                = dwell_index
    self.next_dwell_index           = next_dwell_index
    self.frequency                  = freq_entry["freq"]
    self.duration_meas              = freq_entry["dwell_measurement_time"]
    self.duration_max               = freq_entry["dwell_total_time_max"]
    self.fast_lock_profile_index    = freq_entry["index"]

    dwell_freq = int(round(self.frequency))
    duration_meas = int(self.duration_meas / FAST_CLOCK_PERIOD)
    duration_max = int(self.duration_max / FAST_CLOCK_PERIOD)

    self.hw_dwell_entry = pluto_ecm_hw_dwell.ecm_dwell_entry(1, self.next_dwell_index, self.fast_lock_profile_index, self.dwell_index, dwell_freq, duration_meas, duration_max)
    self.first_dwell    = is_first
    self.last_dwell     = is_last

  #@staticmethod
  #def from_dict(d):
  #  r = dwell_data(d["frequency"], d["dwell_time"])
  #  r.fast_lock_profile_valid    = d["fast_lock_profile_valid"]
  #  r.fast_lock_profile_updated  = d["fast_lock_profile_updated"]
  #  r.fast_lock_profile_data     = d["fast_lock_profile_data"]
  #  r.fast_lock_profile_time     = d["fast_lock_profile_time"]
  #  r.hw_dwell_valid             = d["hw_dwell_valid"]
  #  r.hw_dwell_entry             = pluto_esm_hw_dwell.esm_message_dwell_entry.from_dict(d["hw_dwell_entry"])
  #  r.first_dwell                = d["first_dwell"]
  #  r.last_dwell                 = d["last_dwell"]
  #  return r

  def __str__(self):
    return "[dwell_data: {} {} {} {} {}]".format(self.dwell_index, self.fast_lock_profile_index, self.frequency, self.duration_meas, self.duration_max)
  def __repr__(self):
    return self.__str__()

class fast_lock_cal_state:
  def __init__(self, freq, fast_lock_profile_index):
    self.frequency                  = freq
    self.fast_lock_profile_index    = fast_lock_profile_index
    self.fast_lock_profile_valid    = False
    self.fast_lock_profile_updated  = False
    self.fast_lock_profile_data     = []
    self.fast_lock_profile_time     = 0

  def __str__(self):
    return "[fast_lock_cal_state: {} : {} {} {}]".format(self.frequency, self.fast_lock_profile_index, self.fast_lock_profile_valid, self.fast_lock_profile_data)
  def __repr__(self):
    return self.__str__()


class pluto_ecm_sequencer:

  def __init__(self, logger, recorder, sw_config, hw_interface, analysis_thread, sim_loader):
    self.logger                         = logger
    self.recorder                       = recorder
    self.sw_config                      = sw_config
    self.sim_loader                     = sim_loader
    self.hw_interface                   = hw_interface
    self.dwell_ctrl_interface           = pluto_ecm_hw_dwell.ecm_dwell_controller(hw_interface.hw_cfg)
    self.dwell_reporter                 = pluto_ecm_hw_dwell_reporter.pluto_ecm_hw_dwell_reporter(logger)
    self.drfm_reporter                  = pluto_ecm_hw_drfm_reporter.pluto_ecm_hw_drfm_reporter(logger)
    self.dwell_buffer                   = pluto_ecm_dwell_stats_buffer.pluto_ecm_dwell_stats_buffer(sw_config)
    self.hw_stats                       = pluto_ecm_hw_stats.pluto_ecm_hw_stats(logger)
    self.ecm_controller                 = pluto_ecm_ecm_controller.pluto_ecm_ecm_controller(logger, sw_config, self)

    #self.analysis_thread                = analysis_thread

    self.state                          = "FLUSH"
    self.flush_start_time               = time.time()
    self.flush_delay                    = 1.5

    self.fast_lock_recal_interval       = sw_config.config["fast_lock_config"]["recalibration_interval"]
    self.fast_lock_recal_pause          = sw_config.config["fast_lock_config"]["recalibration_pause"]
    self.fast_lock_cal_pending          = []
    self.fast_lock_last_cal_time        = None
    self.fast_lock_initial_cal_sent     = False
    self.fast_lock_initial_cal_done     = False
    self.current_fast_lock_profiles     = {}

    self.initial_hw_dwells_sent         = False
    self.initial_hw_dwells_loaded       = False

    self.hw_channel_entry_pending       = []
    self.hw_dwell_entry_pending         = []
    self.hw_dwell_program_pending       = []
    self.fast_lock_load_pending         = []

    self.dwell_state                    = "IDLE"
    self.dwell_active                   = []
    self.dwell_active_first             = []
    self.dwell_active_last              = []
    self.dwell_history                  = {}
    self.dwell_rows_to_render           = []

    self.fast_lock_cal_state              = []
    self.dwell_freqs                      = []
    self.dwell_entries                    = []
    self.initial_channel_entries_by_dwell = []
    self.channel_entry_write_queue        = []

    self.report_merge_queue_dwell_summary = []
    self.report_merge_queue_drfm_summary  = {}
    self.report_merge_queue_drfm_channel  = {}

    for entry in sw_config.config["dwell_config"]["dwell_freqs"]:
      assert (entry["index"] == len(self.dwell_freqs))
      self.dwell_freqs.append(entry["freq"])
      self.logger.log(self.logger.LL_INFO, "[sequencer] dwell_freqs: added {}".format(self.dwell_freqs[-1]))

    for entry in sw_config.config["dwell_config"]["dwell_freqs"]:
      self.fast_lock_cal_state.append(fast_lock_cal_state(entry["freq"], entry["index"]))
      self.logger.log(self.logger.LL_INFO, "[sequencer] fast_lock_cal_state: added {}".format(self.fast_lock_cal_state[-1]))

    total_time_meas = 0
    for dwell_index in range(len(sw_config.config["dwell_config"]["dwell_pattern"])):
      freq_index = sw_config.config["dwell_config"]["dwell_pattern"][dwell_index]
      freq_entry = sw_config.config["dwell_config"]["dwell_freqs"][freq_index]
      if dwell_index == (len(sw_config.config["dwell_config"]["dwell_pattern"]) - 1):
        next_dwell_index = 0
        is_last = True
      else:
        next_dwell_index = dwell_index + 1
        is_last = False

      assert (freq_entry["index"] == freq_index)
      self.dwell_entries.append(dwell_data(dwell_index, next_dwell_index, (dwell_index == 0), is_last, freq_entry))
      total_time_meas += freq_entry["dwell_measurement_time"]
      self.logger.log(self.logger.LL_INFO, "[sequencer] dwell_entries added: index={} - {}".format(len(self.dwell_entries) - 1, self.dwell_entries[-1]))

    for dwell_index in range(len(sw_config.config["dwell_config"]["dwell_pattern"])):
      #freq_index = sw_config.config["dwell_config"]["dwell_pattern"][dwell_index]
      #freq_entry = sw_config.config["dwell_config"]["dwell_freqs"][freq_index]
      self.initial_channel_entries_by_dwell.append([])

      for channel_index in range(ECM_NUM_CHANNELS):
        self.initial_channel_entries_by_dwell[-1].append(pluto_ecm_hw_dwell.ecm_channel_control_entry.channel_entry_trigger_none(channel_index))
        self.logger.log(self.logger.LL_INFO, "[sequencer] dwell_entries added: dwell_index={} channel_index={} - {}".format(dwell_index, channel_index, self.initial_channel_entries_by_dwell[-1][-1]))

    #self.scan_total_time = 0
    #self.scan_dwells = {}
    #for freq in sw_config.scan_dwells:
    #  self.scan_dwells[freq] = dwell_data(freq, sw_config.scan_dwells[freq])
    #  self.scan_total_time += self.scan_dwells[freq].dwell_time
    #
    #for freq in self.scan_dwells:
    #  self.logger.log(self.logger.LL_DEBUG, "[sequencer] scan_dwells[{}]=[{}]".format(freq, self.scan_dwells[freq]))

    self.sim_enabled = sw_config.sim_enabled

    self.logger.log(self.logger.LL_INFO, "[sequencer] init done; sim_enabled={}; total_time_meas={}".format(self.sim_enabled, total_time_meas))

#  def _process_data_from_sim(self):
#    entries = self.sim_loader.get_entries_up_to_time(time.time())
#    for entry in entries:
#      if "dwell_report" in entry["data"]:
#        data = entry["data"]["dwell_report"]
#        report = {"dwell_data"        : dwell_data.from_dict(data["dwell_data"]),
#                  "dwell_report"      : data["dwell_report"],
#                  "first_in_sequence" : data["first_in_sequence"],
#                  "last_in_sequence"  : data["last_in_sequence"]}
#        self.logger.log(self.logger.LL_INFO, "[sequencer] _process_data_from_sim: simulated report received for frequency={}".format(report["dwell_data"].frequency))
#        self._process_dwell_report(report)
#      elif "pdw_pulse_report" in entry["data"]:
#        self._process_pdw_report(entry["data"])
#      elif "pdw_summary_report" in entry["data"]:
#        self._process_pdw_report(entry["data"])

  def submit_channel_entry(self, dwell_index, channel_index, channel_entry):
    self.channel_entry_write_queue.append({"dwell_index": dwell_index, "channel_index": channel_index, "channel_entry": channel_entry})
    print("channel_entry_write_queue={}".format(len(self.channel_entry_write_queue)))

  def _flush_channel_entry_queue(self):
    while len(self.channel_entry_write_queue) > 0:
      entry = self.channel_entry_write_queue.pop(0)
      self._send_hw_channel_entry(entry["dwell_index"], entry["channel_index"], entry["channel_entry"])

  def _process_dwell_reports_from_hw(self):
    while len(self.hw_interface.hwdr.output_data_dwell) > 0:
      packed_report = self.hw_interface.hwdr.output_data_dwell.pop(0)
      r = self.dwell_reporter.process_message(packed_report)
      expected_dwell_data = self.dwell_active[0]

      if (r["dwell_entry_frequency"] != int(round(expected_dwell_data.frequency))):
        self.logger.log(self.logger.LL_WARN, "[sequencer] _process_dwell_reports_from_hw: dwell frequency mismatch: received={} expected={}".format(r["dwell_entry_frequency"], int(round(expected_dwell_data.frequency))))
      assert (r["dwell_entry_frequency"] == int(round(expected_dwell_data.frequency)))

      self.logger.log(self.logger.LL_INFO, "[sequencer] _process_dwell_reports_from_hw: report received for frequency={} dwell_seq={}".format(expected_dwell_data.frequency, r["dwell_seq_num"]))
      report = {"dwell_data": expected_dwell_data, "dwell_report": r, "first_in_sequence": expected_dwell_data.first_dwell, "last_in_sequence": expected_dwell_data.last_dwell}
      self.recorder.log({"dwell_report": report})
      self.dwell_active.pop(0)
      self._process_dwell_report(report)
      self.report_merge_queue_dwell_summary.append(report)

  def _process_drfm_reports_from_hw(self):
    while len(self.hw_interface.hwdr.output_data_drfm) > 0:
      packed_report = self.hw_interface.hwdr.output_data_drfm.pop(0)
      r = self.drfm_reporter.process_message(packed_report)
      dwell_seq_num = r["dwell_seq_num"]

      if r["msg_type"] == ECM_REPORT_MESSAGE_TYPE_DRFM_CHANNEL_DATA:
        self.logger.log(self.logger.LL_INFO, "[sequencer] _process_drfm_reports_from_hw: drfm channel report: msg_seq={} dwell_seq={} channel={} iq_bits={} seg_seq={} slice_addr={} slice_len={}".format(
          r["msg_seq_num"], dwell_seq_num, r["channel_index"], r["max_iq_bits"], r["segment_seq_num"], r["slice_addr"], r["slice_length"]))

        report = {"drfm_channel_report": r}
        self.recorder.log(report)
        self._process_drfm_report(report)

        if dwell_seq_num not in self.report_merge_queue_drfm_channel:
          self.report_merge_queue_drfm_channel[dwell_seq_num] = []
        self.report_merge_queue_drfm_channel[dwell_seq_num].append(r)

      elif r["msg_type"] == ECM_REPORT_MESSAGE_TYPE_DRFM_SUMMARY:
        self.logger.log(self.logger.LL_DEBUG, "[sequencer] _process_drfm_reports_from_hw: drfm summary report: msg_seq={} dwell_seq={} chan_written={:04X} chan_read={:04X} dly_chan_wr={} dly_sum_wr={} dly_sum_start={}".format(
          r["msg_seq_num"], r["dwell_seq_num"], r["channel_was_written"], r["channel_was_read"], r["report_delay_channel_write"], r["report_delay_summary_write"], r["report_delay_summary_start"]))

        report = {"drfm_summary_report": r}
        self.recorder.log(report)
        self._process_drfm_report(report)

        self.report_merge_queue_drfm_summary[dwell_seq_num] = r

      else:
        raise RuntimeError("invalid message type")

  def _process_dwell_report(self, report):
    #data for rendering the dwell indicator
    if report["first_in_sequence"]:
      self.dwell_history = {}
    self.dwell_history[report["dwell_data"].frequency] = time.time()

    #self.analysis_thread.submit_report(report) #TODO: use merged data for analysis
    self.hw_stats.submit_report(report)
    #self.ecm_controller.submit_report(report)

    row_done = self.dwell_buffer.process_dwell_update(report)
    if row_done:
      #data for rendering the spectrogram
      self.dwell_rows_to_render.append(report)

  def _process_drfm_report(self, report):
    #self.analysis_thread.submit_report(report) #TODO: use merged data for analysis
    self.hw_stats.submit_report(report)
    #self.ecm_controller.submit_report(report)

  def _process_merged_reports(self):
    while len(self.report_merge_queue_dwell_summary) > 0:

      dwell_seq_num = self.report_merge_queue_dwell_summary[0]["dwell_report"]["dwell_seq_num"]
      if dwell_seq_num not in self.report_merge_queue_drfm_summary:
        break

      dwell_summary         = self.report_merge_queue_dwell_summary.pop(0)
      drfm_summary          = self.report_merge_queue_drfm_summary.pop(dwell_seq_num)
      drfm_channel_reports  = self.report_merge_queue_drfm_channel.pop(dwell_seq_num, None)

      merged_report = {"dwell": dwell_summary, "drfm_summary_report": drfm_summary, "drfm_channel_reports": drfm_channel_reports}
      self.ecm_controller.submit_merged_report(merged_report)

  def _update_data_from_hw(self):
    if self.state == "FLUSH":
      while len(self.hw_interface.hwdr.output_data_dwell) > 0:
        self.logger.log(self.logger.LL_INFO, "[sequencer] _update_data_from_hw: [FLUSH] dropped dwell data")
        self.hw_interface.hwdr.output_data_dwell.pop(0)
      while len(self.hw_interface.hwdr.output_data_drfm) > 0:
        self.logger.log(self.logger.LL_INFO, "[sequencer] _update_data_from_hw: [FLUSH] dropped DRFM data")
        self.hw_interface.hwdr.output_data_drfm.pop(0)
      return
    elif self.state == "IDLE":
      return

    if self.sim_enabled:
      #self._process_data_from_sim()
      raise RuntimeError("sim unsupported")
    else:
      self._process_drfm_reports_from_hw()
      self._process_dwell_reports_from_hw()

    self._process_merged_reports()

  #TODO: cal stuff into separate class
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
    if self.state in ("FLUSH", "IDLE", "SIM"):
      return

    now = time.time()

    #TODO: break out into two functions

    if not self.fast_lock_initial_cal_sent:
      for freq in self.dwell_freqs:
        self.fast_lock_cal_pending.append(freq)
        self.logger.log(self.logger.LL_INFO, "[sequencer] requesting initial fast lock cal for freq={}".format(freq))
        self.hw_interface.send_fast_lock_cal_cmd(freq)

      self.fast_lock_initial_cal_sent = True
      self.logger.log(self.logger.LL_INFO, "[sequencer] initial cal sent")

    if len(self.fast_lock_cal_pending) == 0:
      if (now - self.fast_lock_last_cal_time) < self.fast_lock_recal_pause:
        return

      oldest_cal = self._get_oldest_cal()
      if oldest_cal.fast_lock_profile_valid and ((now - oldest_cal.fast_lock_profile_time) < self.fast_lock_recal_interval):
        return

      self.fast_lock_cal_pending.append(oldest_cal.frequency)
      self.logger.log(self.logger.LL_INFO, "[sequencer] requesting fast lock cal for freq={}: prior_valid={} prior_age={}".format(
        oldest_cal.frequency, oldest_cal.fast_lock_profile_valid, (now - oldest_cal.fast_lock_profile_time)))
      self.hw_interface.send_fast_lock_cal_cmd(oldest_cal.frequency)

    else:
      cal_results = self.hw_interface.check_fast_lock_cal_results()
      if cal_results is None:
        return

      assert (cal_results["freq"] == self.fast_lock_cal_pending[0])
      self.fast_lock_cal_pending.pop(0)
      cal_state = self._get_cal_by_freq(cal_results["freq"])
      cal_state.fast_lock_profile_valid   = True
      cal_state.fast_lock_profile_updated = True
      cal_state.fast_lock_profile_time    = now
      cal_state.fast_lock_profile_data    = cal_results["data"]
      self.fast_lock_last_cal_time        = now
      self.logger.log(self.logger.LL_INFO, "[sequencer] received fast lock cal data for freq={}: {}".format(cal_results["freq"], cal_state.fast_lock_profile_data))

      if not self.fast_lock_initial_cal_done:
        if all([d.fast_lock_profile_valid for d in self.fast_lock_cal_state]):
          self.fast_lock_initial_cal_done = True

  def _send_initial_hw_channel_entries(self):
    for dwell_index in range(len(self.initial_channel_entries_by_dwell)):
      for channel_index in range(ECM_NUM_CHANNELS):
        self._send_hw_channel_entry(dwell_index, channel_index, self.initial_channel_entries_by_dwell[dwell_index][channel_index])

  def _send_initial_hw_dwells(self):
    for entry in self.dwell_entries:
      key = self.dwell_ctrl_interface.send_dwell_entry(entry.dwell_index, entry.hw_dwell_entry)
      self.hw_dwell_entry_pending.append(key)
      self.logger.log(self.logger.LL_INFO, "[sequencer] sending initial hw dwell: uk={} dwell_index={} hw_dwell_entry={}".format(key, entry.dwell_index, entry.hw_dwell_entry))

  def _send_hw_channel_entry(self, dwell_index, channel_index, channel_entry):
    key = self.dwell_ctrl_interface.send_channel_entry(dwell_index, channel_index, channel_entry)
    self.hw_channel_entry_pending.append(key)
    self.logger.log(self.logger.LL_INFO, "[sequencer] sending hw channel entry: uk={} dwell_index={} channel_index={} -> channel_entry={}".format(key, dwell_index, channel_index, channel_entry))

  def _send_hw_dwell_program(self, dwell_program):
    key = self.dwell_ctrl_interface.send_dwell_program(dwell_program)
    self.hw_dwell_program_pending.append(key)
    self.logger.log(self.logger.LL_INFO, "[sequencer] sending dwell program: uk={} dwell_program={}".format(key, dwell_program))

  def _send_fast_lock_profile(self, profile_index, profile_data, force):
    if ((profile_index in self.current_fast_lock_profiles) and (self.current_fast_lock_profiles[profile_index] == profile_data) and (not force)):
      self.logger.log(self.logger.LL_INFO, "[sequencer] skipping fast lock profile, already loaded: index={}".format(profile_index))
      return False

    self.current_fast_lock_profiles[profile_index] = profile_data
    key = self.hw_interface.send_fast_lock_profile(profile_index, profile_data)
    self.fast_lock_load_pending.append(key)
    self.logger.log(self.logger.LL_INFO, "[sequencer] sending fast lock profile: index={} uk={}".format(profile_index, key))
    return True

  def _set_fast_lock_recall(self):
    cmd = pluto_ecm_hw_interface.hw_command.gen_write_attr_dbg(self.hw_interface.hwcp.get_next_unique_key(), "adi,rx-fastlock-pincontrol-enable", "1")
    self.hw_interface.hwcp.send_command(cmd, False)
    key = self.hw_interface.send_fastlock_recall("0")
    self.fast_lock_load_pending.append(key)
    self.logger.log(self.logger.LL_INFO, "[sequencer] fastlock_recall=0")

  #TODO: use a generic function to reduce code duplication
  def _check_pending_hw_dwells(self):
    keys_found = []
    for k in self.hw_dwell_entry_pending:
      if self.hw_interface.hwcp.try_get_result(k) is not None:
        keys_found.append(k)
    for k in keys_found:
      self.hw_dwell_entry_pending.remove(k)
      self.logger.log(self.logger.LL_INFO, "[sequencer] pending hw dwell entry acknowledged -- uk={}".format(k))
    return len(keys_found)

  def _check_pending_hw_channel_entries(self):
    keys_found = []
    for k in self.hw_channel_entry_pending:
      if self.hw_interface.hwcp.try_get_result(k) is not None:
        keys_found.append(k)
    for k in keys_found:
      self.hw_channel_entry_pending.remove(k)
      self.logger.log(self.logger.LL_INFO, "[sequencer] pending hw channel entry acknowledged -- uk={}".format(k))
    return len(keys_found)

  def _check_pending_hw_dwell_programs(self):
    keys_found = []
    for k in self.hw_dwell_program_pending:
      if self.hw_interface.hwcp.try_get_result(k) is not None:
        keys_found.append(k)
    for k in keys_found:
      self.hw_dwell_program_pending.remove(k)
      self.logger.log(self.logger.LL_INFO, "[sequencer] pending hw dwell program acknowledged -- uk={}".format(k))
    return len(keys_found)

  def _check_pending_fast_lock_profiles(self):
    keys_found = []
    for k in self.fast_lock_load_pending:
      if self.hw_interface.hwcp.try_get_result(k) is not None:
        keys_found.append(k)
    for k in keys_found:
      self.fast_lock_load_pending.remove(k)
      self.logger.log(self.logger.LL_INFO, "[sequencer] pending fast lock profile acknowledged -- uk={}".format(k))
    return len(keys_found)

  def _update_hw_dwells(self):
    self._check_pending_hw_channel_entries()
    self._check_pending_hw_dwells()

    if self.state == "LOAD_HW_DWELLS":
      if not self.initial_hw_dwells_sent:
        self._send_initial_hw_channel_entries()
        self._send_initial_hw_dwells()
        self.initial_hw_dwells_sent = True

      if self.initial_hw_dwells_sent and (not self.initial_hw_dwells_loaded):
        if (len(self.hw_dwell_entry_pending) == 0) and (len(self.hw_channel_entry_pending) == 0):
          self.initial_hw_dwells_loaded = True

  def _compute_next_dwell_program(self):
    assert (len(self.dwell_active) > 0)
    return pluto_ecm_hw_dwell.ecm_dwell_program_entry(1, 0, len(self.dwell_active))

  def _activate_next_dwells(self):
    assert (len(self.dwell_active) == 0)

    for dwell_entry in self.dwell_entries:
      self.dwell_active.append(dwell_entry)
      self.logger.log(self.logger.LL_INFO, "[sequencer] _activate_next_dwells: preparing to start new dwell: {}".format(dwell_entry))

    force_fast_lock_update = False
    for cal_entry in self.fast_lock_cal_state:
      force_fast_lock_update |= cal_entry.fast_lock_profile_updated
      cal_entry.fast_lock_profile_updated = False

    fast_lock_profile_sent = False
    for cal_entry in self.fast_lock_cal_state:
      fast_lock_profile_sent |= self._send_fast_lock_profile(cal_entry.fast_lock_profile_index, cal_entry.fast_lock_profile_data, force_fast_lock_update)

    if fast_lock_profile_sent:
      self._set_fast_lock_recall()

  def _update_scan_dwells(self):
    if self.state != "ACTIVE":
      self.dwell_state = "IDLE"
      return

    self._check_pending_fast_lock_profiles()
    self._check_pending_hw_dwell_programs()

    if self.dwell_state == "IDLE":
      self.dwell_state = "LOAD_DWELLS"

    if self.dwell_state == "LOAD_DWELLS":
      self._activate_next_dwells()
      self.dwell_state = "LOAD_PROFILES"

    if self.dwell_state == "LOAD_PROFILES":
      assert (len(self.dwell_active) > 0)
      if len(self.fast_lock_load_pending) == 0:
        self.dwell_state = "SEND_PROGRAM"

        #do channel entry updates -- new thresholds, etc.
        self._flush_channel_entry_queue()

        dwell_program = self._compute_next_dwell_program()
        self._send_hw_dwell_program(dwell_program)
        self.logger.log(self.logger.LL_INFO, "[sequencer] _update_scan_dwells [LOAD_PROFILES]: profiles loaded, sending dwell program")

    if self.dwell_state == "SEND_PROGRAM":
      if len(self.hw_dwell_program_pending) == 0:
        self.logger.log(self.logger.LL_INFO, "[sequencer] _update_scan_dwells [SEND_PROGRAM]: dwell program sent, going active")
        self.dwell_state = "HW_ACTIVE"

    if self.dwell_state == "HW_ACTIVE":
      if (len(self.dwell_active) == 0):
        self.logger.log(self.logger.LL_INFO, "[sequencer] _update_scan_dwells [HW_ACTIVE]: dwells completed")
        self.dwell_state = "DWELLS_COMPLETE"

    if self.dwell_state == "DWELLS_COMPLETE":
      #if len(self.scan_sequence) == 0:
      #  self.dwell_state = "IDLE"
      #else:
      self.dwell_state = "LOAD_DWELLS"

  def update(self):
    cycles_per_update = 5

    for i in range(cycles_per_update):
      if self.state == "FLUSH":
        if (time.time() - self.flush_start_time) > self.flush_delay:
          self.state = "IDLE"
          self.hw_interface.enable_hw()

      elif self.state == "IDLE":
        if self.sim_enabled:
          self.state = "SIM"
        else:
          self.state = "INITIAL_CAL"
      elif self.state == "INITIAL_CAL":
        if self.fast_lock_initial_cal_done:
          self.state = "LOAD_HW_DWELLS"
      elif self.state == "LOAD_HW_DWELLS":
        if self.initial_hw_dwells_loaded:
          self.state = "ACTIVE"
          self.ecm_controller.on_sequencer_active()
      elif self.state == "ACTIVE":
        pass
      elif self.state == "SIM":
        pass

      self._update_data_from_hw()
      self._update_fast_lock_cal()
      self._update_hw_dwells()
      self._update_scan_dwells()
      self.hw_stats.update()
      self.ecm_controller.update()