import time
import random
import json
from pluto_ecm_hw_pkg import *
import pluto_ecm_hw_dwell

class pluto_ecm_ecm_controller:

  def __init__(self, logger, sw_config, sequencer, analysis_thread):
    self.logger           = logger
    self.sw_config        = sw_config
    self.sequencer        = sequencer
    self.analysis_thread  = analysis_thread

    self.state            = "IDLE"
    self.hardware_active  = False

    self.dwell_channels               = []

    self.scan_duration                = 2
    self.forced_triggers_per_cycle    = 8   #TODO: config
    self.prev_pending_forced_triggers = []
    self.scan_pending_forced_triggers = []
    self.scan_forced_trigger_index    = 0

    self.map_state_to_tag             = {"IDLE": 0, "SCAN": 10, "TX_LISTEN": 20}
    self.map_tag_to_state             = {0: "IDLE", 10: "SCAN", 20: "TX_LISTEN"}
    self.dwell_program_tag            = self.map_state_to_tag[self.state]

    #TODO: render_status: show controller state, forced trigger index/total

    for channel_index in range(ECM_NUM_CHANNELS):
      for dwell_index in range(len(sw_config.config["dwell_config"]["dwell_pattern"])):
        if (ECM_CHANNEL_MASK & (1 << channel_index)) != 0:
          self.dwell_channels.append({"dwell_index": dwell_index, "channel_index": channel_index})

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

      #self.logger.log(self.logger.LL_INFO, "[ecm_controller] _send_next_forced_triggers: next_index={}; forcing {}/{}".format(self.scan_forced_trigger_index, next_dwell_index, next_channel_index))
      self.sequencer.submit_channel_entry(next_dwell_index, next_channel_index, next_entry)

      self.scan_pending_forced_triggers.append({"dwell_index": next_dwell_index, "channel_index": next_channel_index, "expected_bytes": next_entry.fields["trigger_duration_max_minus_one"] + 1})
      self.prev_pending_forced_triggers.append({"dwell_index": next_dwell_index, "channel_index": next_channel_index})
      self.scan_forced_trigger_index = (self.scan_forced_trigger_index + 1) % len(self.dwell_channels)

  def submit_report(self, merged_report):
    #self.logger.log(self.logger.LL_INFO, "[ecm_controller] submit_report: {}".format(merged_report))

    if merged_report["drfm_channel_reports"] is None:
      self.analysis_thread.submit_data({"scan_report_bare": merged_report, "state": self.state})

    else:
      if (self.state == "TX_LISTEN") or (self.state == "TX_ACTIVE"):
        assert (len(self.scan_pending_forced_triggers) == 0)
        self.analysis_thread.submit_data({"scan_report_iq": merged_report, "state": self.state})
      else:
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
              self.scan_pending_forced_triggers.pop(0)
              full_match = True
              self.logger.log(self.logger.LL_INFO, "[ecm_controller] submit_report: matched dwell_index={} channel_index={}".format(expected_dwell_index, expected_channel_index))

        assert (not partial_match or full_match)
        if full_match:
          self.analysis_thread.submit_data({"scan_report_iq": merged_report, "state": self.state})
        else:
          self.logger.log(self.logger.LL_INFO, "[ecm_controller] submit_report: match failed: expected={}/{}, report={}".format(expected_dwell_index, expected_channel_index, merged_report))
          print("match failed")

  def on_sequencer_active(self):
    self.hardware_active  = True

    self._set_new_state("SCAN")
    self.scan_start_time  = time.time()
    self.analysis_thread.submit_data({"command": "SCAN_START"})

  def on_dwell_row_done(self):
    pass

  def on_dwell_state_update(self, dwell_state):
    pass

  def _set_new_state(self, new_state):
    self.state              = new_state
    self.dwell_program_tag  = self.map_state_to_tag[new_state]

  def update_state(self):
    if self.state == "SCAN":
      if len(self.scan_pending_forced_triggers) == 0:
        if (time.time() - self.scan_start_time) > self.scan_duration:
          self._clear_prev_forced_triggers()
          self.logger.log(self.logger.LL_INFO, "[ecm_controller] scan complete - starting TX_LISTEN")
          self._set_new_state("TX_LISTEN")

          self.analysis_thread.submit_data({"command": "SCAN_END"})
        else:
          self._send_next_forced_triggers()
    elif self.state == "TX_LISTEN":
      pass

  def update(self):
    self.update_state()

    pass