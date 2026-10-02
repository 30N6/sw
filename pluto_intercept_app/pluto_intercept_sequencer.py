import time
import random
import json
from pluto_intercept_hw_pkg import *
import pluto_intercept_hw_stats
import pluto_intercept_hw_interface
import pluto_intercept_hw_control
import pluto_intercept_hw_dwell_reporter
import pluto_intercept_hw_stream_reporter

import cProfile, pstats, io
from pstats import SortKey

class pluto_intercept_sequencer:

  def __init__(self, logger, recorder, sw_config, hw_interface, analysis_thread, sim_loader):
    self.logger                         = logger
    self.recorder                       = recorder
    self.sw_config                      = sw_config
    self.sim_loader                     = sim_loader
    self.hw_interface                   = hw_interface
    self.hw_control                     = pluto_intercept_hw_control.intercept_hardware_control(hw_interface.hw_cfg)
    self.dwell_reporter                 = pluto_intercept_hw_dwell_reporter.pluto_intercept_hw_dwell_reporter(logger)
    self.stream_reporter                = pluto_intercept_hw_stream_reporter.pluto_intercept_hw_stream_reporter(logger)
    self.hw_stats                       = pluto_intercept_hw_stats.pluto_intercept_hw_stats(logger)

    self.analysis_thread                = analysis_thread

    self.sim_enabled                    = sw_config.sim_enabled
    self.state                          = "INIT"

    self.hw_dwell_entry_pending         = []
    self.hw_channel_entry_pending       = []
    self.hw_stream_entry_pending        = []

    self.dwells_to_render               = []
    self.streams_to_render              = []

    self.channel_entry_write_queue      = []
    self.stream_entry_write_queue       = []

    self.pr = cProfile.Profile()

    self.dwell_data                     = sw_config.dwell_data
    self.dwell_entry                    = pluto_intercept_hw_control.intercept_dwell_control_entry(1, 0, int(self.dwell_data["frequency"] * 1e3), self.dwell_data["window_duration"])

    self.channel_entries = []
    for i in range(INTERCEPT_NUM_CHANNELS):
      self.channel_entries.append(pluto_intercept_hw_control.intercept_channel_control_entry(1, 0, 0, 0, 0xFFFFFFFF, 0xFFFFFFFF, 0, 0))

    self.stream_entries = []
    for i in range(INTERCEPT_NUM_STREAMS):
      self.stream_entries.append(pluto_intercept_hw_control.intercept_stream_control_entry(i < (INTERCEPT_NUM_STREAMS - 1), 0))

    self.logger.log(self.logger.LL_INFO, "[sequencer] init done; sim_enabled={} frequency={} window_duration={}".format(self.sim_enabled, self.dwell_data["frequency"], self.dwell_data["window_duration"]))

  def submit_channel_entry(self, index, entry):
    self.logger.log(self.logger.LL_INFO, "[sequencer] submit_channel_entry: index={} entry={}".format(index, entry))
    self.channel_entry_write_queue.append({"index": index, "entry": entry})

  def submit_stream_entry(self, index, entry):
    self.logger.log(self.logger.LL_INFO, "[sequencer] submit_stream_entry: index={} entry={}".format(index, entry))
    self.stream_entry_write_queue.append({"index": index, "entry": entry})

  def _flush_channel_entry_queue(self):
    if len(self.channel_entry_write_queue) > 0:
      self.logger.log(self.logger.LL_INFO, "[sequencer] _flush_channel_entry_queue: num_entries={}".format(len(self.channel_entry_write_queue)))

    while len(self.channel_entry_write_queue) > 0:
      entry = self.channel_entry_write_queue.pop(0)
      self._send_hw_channel_entry(entry["index"], entry["entry"])

  def _flush_stream_entry_queue(self):
    if len(self.stream_entry_write_queue) > 0:
      self.logger.log(self.logger.LL_INFO, "[sequencer] _flush_stream_entry_queue: num_entries={}".format(len(self.stream_entry_write_queue)))

    while len(self.stream_entry_write_queue) > 0:
      entry = self.stream_entry_write_queue.pop(0)
      self._send_hw_stream_entry(entry["index"], entry["entry"])

  def _send_hw_dwell_entry(self, data):
    key = self.hw_control.send_dwell_entry(data)
    self.hw_dwell_entry_pending.append(key)
    self.logger.log(self.logger.LL_INFO, "[sequencer] sending hw dwell entry: uk={} data={}".format(key, data))

  def _send_hw_channel_entry(self, channel_index, channel_entry):
    key = self.hw_control.send_channel_entry(channel_index, channel_entry)
    self.hw_channel_entry_pending.append(key)
    self.logger.log(self.logger.LL_INFO, "[sequencer] sending hw channel entry: uk={} channel_index={} -> channel_entry={}".format(key, channel_index, channel_entry))

  def _send_hw_stream_entry(self, stream_index, stream_entry):
    key = self.hw_control.send_stream_entry(stream_index, stream_entry)
    self.hw_stream_entry_pending.append(key)
    self.logger.log(self.logger.LL_INFO, "[sequencer] sending hw stream entry: uk={} stream_index={} -> stream_entry={}".format(key, stream_index, stream_entry))

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

  def _check_pending_hw_stream_entries(self):
    keys_found = []
    for k in self.hw_stream_entry_pending:
      if self.hw_interface.hwcp.try_get_result(k) is not None:
        keys_found.append(k)
    for k in keys_found:
      self.hw_stream_entry_pending.remove(k)
      self.logger.log(self.logger.LL_INFO, "[sequencer] pending hw dwell program acknowledged -- uk={}".format(k))
    return len(keys_found)

  def _process_dwell_reports_from_hw(self):
    while len(self.hw_interface.hwdr.output_data_dwell) > 0:
      packed_report = self.hw_interface.hwdr.output_data_dwell.pop(0)
      r = self.dwell_reporter.process_message(packed_report)

      if r is None:
        continue

      self.logger.log(self.logger.LL_INFO, "[sequencer] _process_dwell_reports_from_hw: full report received = {}".format(r)) #TODO: reduce logging
      self.recorder.log({"dwell_report": r})

      self.hw_stats.submit_report(r)
      self.dwells_to_render.append(r)

  def _process_stream_reports_from_hw(self):
    while len(self.hw_interface.hwdr.output_data_stream) > 0:
      packed_report = self.hw_interface.hwdr.output_data_stream.pop(0)
      r = self.stream_reporter.process_message(packed_report)

      report = {"stream_report": r}
      self.logger.log(self.logger.LL_INFO, "[sequencer] _process_stream_reports_from_hw: report received = {}".format(r)) #TODO: reduce logging
      self.recorder.log(report)

      self.hw_stats.submit_report(report)
      self.streams_to_render.append(report)

  def _send_initial_hw_control(self):
    for i in len(self.channel_entries):
      self._send_hw_channel_entry(i, self.channel_entries[i])

    for i in len(self.stream_entries):
      self._send_hw_stream_entry(i, self.stream_entries[i])

    self._send_hw_dwell_entry(self.dwell_entry)

  def _update_hw_reports(self):
    if self.state == "IDLE":
      return

    if self.sim_enabled:
      #self._process_data_from_sim()
      raise RuntimeError("sim unsupported")
    else:
      self._process_stream_reports_from_hw()
      self._process_dwell_reports_from_hw()

  def _update_hw_acks(self):
    self._check_pending_hw_dwells()
    self._check_pending_hw_channel_entries()
    self._check_pending_hw_stream_entries()

  def update(self):
    #start = time.time()
    #self.pr.enable()

    cycles_per_update = 5

    for i in range(cycles_per_update):
      if self.state == "IDLE":
        if self.sim_enabled:
          self.state = "SIM"
        else:
          self.state = "INIT_START"

      elif self.state == "INIT_START":
        self.state = "INIT_WAIT"
        self.hw_interface.enable_hw()
        self._send_initial_hw_control()

      elif self.state == "INIT_WAIT":
        if (len(self.hw_dwell_entry_pending) == 0) and (len(self.hw_channel_entry_pending) == 0) and (len(self.hw_stream_entry_pending) == 0):
          self.state = "ACTIVE"

      elif self.state == "ACTIVE":
        pass

      elif self.state == "SIM":
        pass

      self._update_hw_reports()
      self._update_hw_acks()
      self.hw_stats.update()

      #self.ecm_controller.update()

    #print("pluto_ecm_sequencer: {:.3f}".format(time.time() - start))
    #self.pr.disable()
    #s = io.StringIO()
    #sortby = SortKey.CUMULATIVE
    #ps = pstats.Stats(self.pr, stream=s).sort_stats(sortby)
    #ps.print_stats()
    #print(s.getvalue())

  def process_keystate(self, key_state):
    pass
    #self.ecm_controller.process_keystate(key_state)
