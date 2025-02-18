import pygame
import time
import random
import json
from pluto_ecm_hw_pkg import *
import pluto_ecm_hw_dwell
import pluto_ecm_tx_program

class pluto_ecm_ecm_controller:

  def __init__(self, logger, sw_config, sequencer, analysis_thread):
    self.logger             = logger
    self.sw_config          = sw_config
    self.sequencer          = sequencer
    self.analysis_thread    = analysis_thread
    self.tx_program_loader  = pluto_ecm_tx_program.pluto_ecm_tx_program(sw_config.config, sw_config.filename)

    self.state            = "IDLE"
    self.hardware_active  = False
    self.tx_key_active    = False

    self.dwell_channels               = []

    self.start_time_scan              = 0
    self.start_time_tx_listen         = 0
    self.start_time_tx_active         = 0
    self.duration_scan                = 2
    self.duration_tx_listen           = 50 #TODO: config

    self.forced_triggers_per_cycle    = 8   #TODO: config
    self.prev_pending_forced_triggers = []
    self.scan_pending_forced_triggers = []
    self.scan_forced_trigger_index    = 0

    self.map_state_to_tag             = {"IDLE": 0, "SCAN": 10, "TX_LISTEN": 20, "TX_ACTIVE": 30}
    self.map_tag_to_state             = {0: "IDLE", 10: "SCAN", 20: "TX_LISTEN", 30: "TX_ACTIVE"}
    self.dwell_program_tag            = self.map_state_to_tag[self.state]

    self.last_scan_seq_num              = -1
    self.dwell_trigger_threshold_level  = {}
    self.dwell_trigger_threshold_shift  = {}
    self.dwell_trigger_offset_dB        = {}
    self.dwell_trigger_hyst_dB          = {}
    self.dwell_channel_freq             = {}
    self.dwell_tx_enabled               = {}

    self.signals_for_tx                 = []
    self.tx_channels_active             = []

    for channel_index in range(ECM_NUM_CHANNELS):
      for dwell_index in range(len(sw_config.config["dwell_config"]["dwell_pattern"])):
        freq_index = sw_config.config["dwell_config"]["dwell_pattern"][dwell_index]
        freq_entry = sw_config.config["dwell_config"]["dwell_freqs"][freq_index]

        if (ECM_CHANNEL_MASK & (1 << channel_index)) != 0:
          self.dwell_channels.append({"dwell_index": dwell_index,
                                      "channel_index": channel_index,
                                      "dwell_freq": freq_entry["freq"],
                                      "channel_freq": [freq_entry["freq"] + 1e-6 * (ADC_CLOCK_FREQUENCY / ECM_NUM_CHANNELS) * (channel_index - ECM_NUM_CHANNELS/2) for i in range(ECM_NUM_CHANNELS)]})

    for freq_entry in sw_config.config["dwell_config"]["dwell_freqs"]:
      self.dwell_trigger_threshold_level[freq_entry["freq"]]  = [0xFFFFFFFF for i in range(ECM_NUM_CHANNELS)]
      self.dwell_trigger_threshold_shift[freq_entry["freq"]]  = [1 for i in range(ECM_NUM_CHANNELS)]
      self.dwell_trigger_offset_dB[freq_entry["freq"]]        = [None for i in range(ECM_NUM_CHANNELS)]
      self.dwell_trigger_hyst_dB[freq_entry["freq"]]          = [None for i in range(ECM_NUM_CHANNELS)]
      self.dwell_channel_freq[freq_entry["freq"]]             = [freq_entry["freq"] + 1e-6 * (ADC_CLOCK_FREQUENCY / ECM_NUM_CHANNELS) * (i - ECM_NUM_CHANNELS/2) for i in range(ECM_NUM_CHANNELS)]
      self.dwell_tx_enabled[freq_entry["freq"]]               = freq_entry["tx_enabled"]

      for channel_index in range(ECM_NUM_CHANNELS):
        channel_freq = self.dwell_channel_freq[freq_entry["freq"]][channel_index]

        min_threshold = None
        max_hyst = None
        for signal_entry in sw_config.config["tx_config"]["signals"]:
          if (channel_freq >= signal_entry["freq_range"][0]) and (channel_freq <= signal_entry["freq_range"][1]):
            if min_threshold is None:
              min_threshold = signal_entry["threshold_dB"]
            else:
              min_threshold = min(signal_entry["threshold_dB"], min_threshold)
            if max_hyst is None:
              max_hyst = signal_entry["threshold_hyst_dB"]
            else:
              max_hyst = max(signal_entry["threshold_hyst_dB"], max_hyst)

        self.dwell_trigger_offset_dB[freq_entry["freq"]][channel_index] = min_threshold
        self.dwell_trigger_hyst_dB[freq_entry["freq"]][channel_index] = max_hyst

  def _write_tx_programs_to_hw(self):
    for name, entry in self.tx_program_loader.tx_programs_by_name.items():
      self.logger.log(self.logger.LL_INFO, "[ecm_controller] sending tx program: name={} address={}".format(name, entry["address"]))
      self.sequencer.submit_tx_program(entry)

  def _clear_prev_forced_triggers(self):
    for entry in self.prev_pending_forced_triggers:
      #self.logger.log(self.logger.LL_INFO, "[ecm_controller] _send_next_forced_triggers: clearing {}/{}".format(entry["dwell_index"], entry["channel_index"]))
      self.sequencer.submit_channel_entry(entry["dwell_index"], entry["channel_index"], pluto_ecm_hw_dwell.ecm_channel_control_entry.channel_entry_trigger_none(entry["channel_index"]))
    self.prev_pending_forced_triggers = []

  def _send_next_forced_triggers(self):
    assert (len(self.scan_pending_forced_triggers) == 0)

    self._clear_prev_forced_triggers()

    for i in range(self.forced_triggers_per_cycle):
      next_dwell_index    = self.dwell_channels[self.scan_forced_trigger_index]["dwell_index"]
      next_channel_index  = self.dwell_channels[self.scan_forced_trigger_index]["channel_index"]
      next_entry          = pluto_ecm_hw_dwell.ecm_channel_control_entry.channel_entry_trigger_forced(next_channel_index)

      self.logger.log(self.logger.LL_INFO, "[ecm_controller] _send_next_forced_triggers: next_index={}; forcing {}/{}".format(self.scan_forced_trigger_index, next_dwell_index, next_channel_index))
      self.sequencer.submit_channel_entry(next_dwell_index, next_channel_index, next_entry)

      self.scan_pending_forced_triggers.append({"dwell_index": next_dwell_index, "channel_index": next_channel_index, "expected_bytes": next_entry.fields["trigger_duration_max_minus_one"] + 1})
      self.prev_pending_forced_triggers.append({"dwell_index": next_dwell_index, "channel_index": next_channel_index})
      self.scan_forced_trigger_index = (self.scan_forced_trigger_index + 1) % len(self.dwell_channels)

    ##2425.0, 'channel_freq': 2401.96
    #self._submit_channel_threshold_trigger_with_tx(2425.0, 2, 10000, 3,
    #                                               1, self.tx_program_loader.tx_programs_by_name["tx_program_elrs_test_1.json"]["address"],
    #                                               100, 4000)

  def submit_report(self, merged_report):
    #self.logger.log(self.logger.LL_INFO, "[ecm_controller] submit_report: {}".format(merged_report))

    #TODO: use reported program_tag instead of current state - more robust?

    if merged_report["drfm_channel_reports"] is None:
      self.analysis_thread.submit_data({"scan_report_bare": merged_report, "state": self.state, "timestamp": time.time()})

    else:
      if (self.state == "TX_LISTEN") or (self.state == "TX_ACTIVE"):
        assert (len(self.scan_pending_forced_triggers) == 0)
        self.analysis_thread.submit_data({"scan_report_iq": merged_report, "state": self.state, "timestamp": time.time()})

      elif (self.state == "SCAN"):
        self.analysis_thread.submit_data({"scan_report_iq": merged_report, "state": self.state, "timestamp": time.time()})

        if len(self.scan_pending_forced_triggers) == 0:
          return

        expected_trigger        = self.scan_pending_forced_triggers[0]
        expected_dwell_index    = expected_trigger["dwell_index"]
        expected_channel_index  = expected_trigger["channel_index"]

        if merged_report["dwell"]["dwell_data"].dwell_index != expected_dwell_index:
          return

        partial_match = False
        full_match = False
        for entry in merged_report["drfm_channel_reports"]:
          if entry["channel_index"] == expected_channel_index:
            expected_trigger["expected_bytes"] -= entry["slice_length"]
            partial_match = True
            if expected_trigger["expected_bytes"] <= 0:
              self.logger.log(self.logger.LL_INFO, "[ecm_controller] submit_report: matched -- len={} expected_trigger={} entry={}".format(len(self.scan_pending_forced_triggers), expected_trigger, entry))
              full_match = True
              self.logger.log(self.logger.LL_INFO, "[ecm_controller] submit_report: matched dwell_index={} channel_index={}".format(expected_dwell_index, expected_channel_index))

              self.scan_pending_forced_triggers.pop(0)
              if len(self.scan_pending_forced_triggers) > 0:
                expected_trigger        = self.scan_pending_forced_triggers[0]
                expected_dwell_index    = expected_trigger["dwell_index"]
                expected_channel_index  = expected_trigger["channel_index"]
              else:
                break

        #assert (not partial_match or full_match)
        if not full_match:
          self.logger.log(self.logger.LL_INFO, "[ecm_controller] submit_report: match failed: expected={}/{}, report={}".format(expected_dwell_index, expected_channel_index, merged_report))

      else:
        self.logger.log(self.logger.LL_INFO, "[ecm_controller] submit_report: dropped, state={}".format(self.state))

  def on_sequencer_active(self):
    self.hardware_active = True
    self._write_tx_programs_to_hw()
    self.state_start_scan()

  def on_dwell_row_done(self):
    pass

  def on_dwell_state_update(self, dwell_state):
    pass

  def _set_new_state(self, new_state):
    self.state              = new_state
    self.dwell_program_tag  = self.map_state_to_tag[new_state]

  def _submit_channel_threshold_trigger_listen_only(self, dwell_freq, channel_index, threshold_level, threshold_shift):
    self.logger.log(self.logger.LL_INFO, "[ecm_controller] _submit_channel_threshold_trigger_listen_only: dwell_freq={} channel_index={} threshold_level={} threshold_shift={}".format(
      dwell_freq, channel_index, threshold_level, threshold_shift))

    channel_entry = pluto_ecm_hw_dwell.ecm_channel_control_entry.channel_entry_trigger_threshold_listen_only(channel_index, threshold_level, threshold_shift)

    for entry in self.dwell_channels:
      if (entry["dwell_freq"] != dwell_freq) or (entry["channel_index"] != channel_index):
        continue
      self.sequencer.submit_channel_entry(entry["dwell_index"], channel_index, channel_entry)

  def _submit_channel_threshold_trigger_with_tx(self, dwell_freq, channel_index, threshold_level, threshold_shift, tx_trigger_immediate_after_min, tx_instruction_index, tx_duration_min_minus_one, tx_duration_max_minus_one):
    self.logger.log(self.logger.LL_INFO, "[ecm_controller] _submit_channel_threshold_trigger_with_tx: dwell_freq={} channel_index={} threshold_level={} threshold_shift={} tx_immediate={} tx_inst_index={} tx_duration_min={} tx_duration_max={}".format(
      dwell_freq, channel_index, threshold_level, threshold_shift, tx_trigger_immediate_after_min, tx_instruction_index, tx_duration_min_minus_one, tx_duration_max_minus_one))

    program_entries = [pluto_ecm_hw_dwell.ecm_channel_tx_program_entry(0, 0, 0, 0, 0) for i in range(ECM_NUM_CHANNEL_TX_PROGRAM_ENTRIES)]
    program_entries[0] = pluto_ecm_hw_dwell.ecm_channel_tx_program_entry(1, tx_trigger_immediate_after_min, tx_instruction_index, tx_duration_min_minus_one, tx_duration_max_minus_one)
    channel_entry = pluto_ecm_hw_dwell.ecm_channel_control_entry.channel_entry_trigger_threshold_tx(channel_index, threshold_level, threshold_shift, program_entries)

    for entry in self.dwell_channels:
      if (entry["dwell_freq"] != dwell_freq) or (entry["channel_index"] != channel_index):
        continue
      self.sequencer.submit_channel_entry(entry["dwell_index"], channel_index, channel_entry)

  def _get_hyst_shift(self, hyst_dB):
    hyst_factor = int(round(10**(hyst_dB/10)))

    for hyst_shift in range(2**ECM_DRFM_SEGMENT_HYST_SHIFT_WIDTH):
      hyst_v = (1 << hyst_shift)
      if hyst_v >= hyst_factor:
        break

    return hyst_shift

  def _update_thresholds_from_scan(self):
    if self.last_scan_seq_num == self.analysis_thread.scan_seq_num:
      return

    self.last_scan_seq_num = self.analysis_thread.scan_seq_num

    for dwell_freq in self.dwell_trigger_threshold_level:
      if dwell_freq not in self.analysis_thread.scan_results:
        continue

      for i in range(ECM_NUM_CHANNELS):
        if (ECM_CHANNEL_MASK & (1 << i)) == 0:
          continue

        if (self.dwell_trigger_offset_dB[dwell_freq][i] is None) or (self.dwell_trigger_hyst_dB[dwell_freq][i] is None):
          continue

        threshold_offset_dB   = self.dwell_trigger_offset_dB[dwell_freq][i]
        threshold_hyst_dB     = self.dwell_trigger_hyst_dB[dwell_freq][i]
        channel_power         = self.analysis_thread.scan_results[dwell_freq]["summary_power_median"][i]
        threshold_power       = int(round(channel_power * 10**(threshold_offset_dB/10)))
        threshold_hyst_shift  = self._get_hyst_shift(threshold_hyst_dB)

        self.dwell_trigger_threshold_level[dwell_freq][i] = threshold_power
        self.dwell_trigger_threshold_shift[dwell_freq][i] = threshold_hyst_shift
        self._submit_channel_threshold_trigger_listen_only(dwell_freq, i, threshold_power, threshold_hyst_shift)

  def _update_hardware_tx_active_start(self):
    #TODO: similar scheme to _update_thresholds -- wait for tx_listen seq num to change -- need to make sure next state is active, not scan

    self.tx_channels_active = []

    for dwell_freq in self.dwell_trigger_threshold_level:
      if not self.dwell_tx_enabled[dwell_freq]:
        continue

      for i in range(ECM_NUM_CHANNELS):
        if (ECM_CHANNEL_MASK & (1 << i)) == 0:
          continue

        if (self.dwell_trigger_offset_dB[dwell_freq][i] is None) or (self.dwell_trigger_hyst_dB[dwell_freq][i] is None):
          continue

        channel_match = False
        for signal_entry in self.signals_for_tx:
          if signal_entry["agile"]:
            if signal_entry["freq"] == dwell_freq:
              channel_match = True
              break
          else:
            if signal_entry["freq"] == self.dwell_channel_freq[dwell_freq][i]:
              channel_match = True
              break

        if not channel_match:
          continue

        threshold_level = self.dwell_trigger_threshold_level[dwell_freq][i]
        threshold_shift = self.dwell_trigger_threshold_shift[dwell_freq][i]

        tx_parameters = signal_entry["tx_parameters"]
        if len(tx_parameters["tx_program"]) == 0:
          continue

        trigger_duration_min_minus_one = min(tx_parameters["trigger_duration"][0] - 1, 4095)
        trigger_duration_max_minus_one = min(tx_parameters["trigger_duration"][1] - 1, 4095)

        signal_entry["tx_enabled"]      = True
        signal_entry["threshold_level"] = min(signal_entry["threshold_level"], threshold_level)
        signal_entry["threshold_shift"] = max(signal_entry["threshold_shift"], threshold_shift)

        tx_entry = {"dwell_freq": dwell_freq, "channel_index": i, "threshold_level": threshold_level, "threshold_shift": threshold_shift}
        self.tx_channels_active.append(tx_entry)
        self.logger.log(self.logger.LL_INFO, "[ecm_controller] _update_hardware_tx_active_start: channel enabled: {}".format(tx_entry))

        self._submit_channel_threshold_trigger_with_tx(dwell_freq, i, threshold_level, threshold_shift,
                                                       tx_parameters["immediate_tx"], self.tx_program_loader.tx_programs_by_name[tx_parameters["tx_program"]]["address"],
                                                       trigger_duration_min_minus_one, trigger_duration_max_minus_one)

  def _update_hardware_tx_active_end(self):
    while len(self.tx_channels_active) > 0:
      tx_entry = self.tx_channels_active.pop(0)
      self.logger.log(self.logger.LL_INFO, "[ecm_controller] _update_hardware_tx_active_end: reverting channel: {}".format(tx_entry))
      self._submit_channel_threshold_trigger_listen_only(tx_entry["dwell_freq"], tx_entry["channel_index"], tx_entry["threshold_level"], tx_entry["threshold_shift"])

  def _update_state(self):
    if self.state == "SCAN":
      if len(self.scan_pending_forced_triggers) == 0:
        if (time.time() - self.start_time_scan) > self.duration_scan:
          self._clear_prev_forced_triggers()
          self.logger.log(self.logger.LL_INFO, "[ecm_controller] scan complete - starting TX_LISTEN")
          self.analysis_thread.submit_data({"command": "SCAN_END", "timestamp": time.time()})
          self.state_start_tx_listen()

        else:
          self._send_next_forced_triggers()

    elif self.state == "TX_LISTEN":
      if self.tx_key_active:
        self.logger.log(self.logger.LL_INFO, "[ecm_controller] exiting tx_listen - starting tx_active")
        self.analysis_thread.submit_data({"command": "TX_LISTEN_END", "timestamp": time.time()})
        self.state_start_tx_active()
      elif (time.time() - self.start_time_tx_listen) > self.duration_tx_listen:
        self.logger.log(self.logger.LL_INFO, "[ecm_controller] exiting tx_listen - starting scan")
        self.analysis_thread.submit_data({"command": "TX_LISTEN_END", "timestamp": time.time()})
        self.state_start_scan()

    elif self.state == "TX_ACTIVE":
      if not self.tx_key_active:
        self.signals_for_tx = []
        self._update_hardware_tx_active_end()
        self.logger.log(self.logger.LL_INFO, "[ecm_controller] exiting tx_active - starting tx_listen")
        self.analysis_thread.submit_data({"command": "TX_ACTIVE_END", "timestamp": time.time()})
        self.state_start_tx_listen()

  def state_start_scan(self):
    self._set_new_state("SCAN")
    self.start_time_scan = time.time()
    self.analysis_thread.submit_data({"command": "SCAN_START", "timestamp": time.time()})

  def state_start_tx_listen(self):
    self._set_new_state("TX_LISTEN")
    self.start_time_tx_listen = time.time()
    self.analysis_thread.submit_data({"command": "TX_LISTEN_START", "timestamp": time.time()})

  def state_start_tx_active(self):
    now = time.time()
    self.signals_for_tx = []
    for entry in self.analysis_thread.signals_confirmed:
      tx_entry = {"name"            : entry["name"],
                  "freq"            : entry["freq"],
                  "agile"           : entry["agile"],
                  "tx_parameters"   : entry["tx_parameters"],
                  "tx_enabled"      : False,
                  "threshold_level" : 0xFFFFFFFF,
                  "threshold_shift" : 0,
                  "timestamp"       : now}
      self.signals_for_tx.append(tx_entry)
    self._set_new_state("TX_ACTIVE")
    self.start_time_tx_active = time.time()
    self.analysis_thread.submit_data({"command": "TX_ACTIVE_START", "timestamp": time.time()})

    self._update_hardware_tx_active_start()

  def update(self):
    self._update_state()
    self._update_thresholds_from_scan()

  def process_keystate(self, key_state):
    self.tx_key_active = key_state[pygame.K_TAB]
