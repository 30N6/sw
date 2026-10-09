import time
import random
import json
from pluto_intercept_hw_pkg import *
import pluto_intercept_hw_stats
import pluto_intercept_hw_interface
import pluto_intercept_hw_control
import pluto_intercept_hw_dwell_reporter
import pluto_intercept_hw_stream_reporter
import pluto_intercept_threshold_control

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
    self.threshold_control              = pluto_intercept_threshold_control.pluto_intercept_threshold_control(logger, sw_config, self)

    self.analysis_thread                = analysis_thread

    self.sim_enabled                    = sw_config.sim_enabled
    self.state                          = "IDLE"
    self.last_watchdog_update           = 0

    self.hw_dwell_entry_pending         = []
    self.hw_channel_entry_pending       = []
    self.hw_stream_entry_pending        = []

    self.dwells_to_render               = []
    #self.streams_to_render              = [] #todo

    self.channel_entry_write_queue      = []
    self.stream_entry_write_queue       = []
    self.dwell_entry_write_queue        = []

    self.pr = cProfile.Profile()

    self.dwell_data                     = sw_config.dwell_data
    self.dwell_entry                    = None
    self.channel_entries                = {}
    self.stream_entries                 = {}

    self.channel_frequency              = [self.dwell_data["frequency"] + (i - (INTERCEPT_NUM_CHANNELS / 2)) * (ADC_CLOCK_FREQUENCY * 1e-6 / INTERCEPT_NUM_CHANNELS) for i in range(INTERCEPT_NUM_CHANNELS)]
    self.channel_frequency_str          = ["{:.3f}".format(self.channel_frequency[i]) for i in range(INTERCEPT_NUM_CHANNELS)]

    self.stream_last_trigger_type       = np.ones(INTERCEPT_NUM_STREAMS, dtype=np.uint32) * 3
    self.stream_last_channel_index      = np.zeros(INTERCEPT_NUM_STREAMS, dtype=np.uint32)
    self.stream_last_sample_index       = np.zeros(INTERCEPT_NUM_STREAMS, dtype=np.uint32)
    self.stream_last_frequency          = np.zeros(INTERCEPT_NUM_STREAMS)
    self.stream_last_frequency_str      = ["" for i in range(INTERCEPT_NUM_STREAMS)]


    self.logger.log(self.logger.LL_INFO, "[sequencer] init done; sim_enabled={} frequency={} window_duration={}".format(self.sim_enabled, self.dwell_data["frequency"], self.dwell_data["window_duration"]))

  def submit_dwell_entry(self, entry):
    self.logger.log(self.logger.LL_DEBUG, "[sequencer] submit_dwell_entry: entry={}".format(entry))
    self.dwell_entry_write_queue.append(entry)

  def submit_channel_entry(self, index, entry):
    self.logger.log(self.logger.LL_DEBUG, "[sequencer] submit_channel_entry: index={} entry={}".format(index, entry))
    self.channel_entry_write_queue.append({"index": index, "entry": entry})

  def submit_stream_entry(self, index, entry):
    self.logger.log(self.logger.LL_DEBUG, "[sequencer] submit_stream_entry: index={} entry={}".format(index, entry))
    self.stream_entry_write_queue.append({"index": index, "entry": entry})

  def _flush_dwell_entry_queue(self):
    if len(self.dwell_entry_write_queue) > 0:
      self.logger.log(self.logger.LL_DEBUG, "[sequencer] _flush_channel_entry_queue: num_entries={}".format(len(self.dwell_entry_write_queue)))

    for entry in self.dwell_entry_write_queue:
      self._send_hw_dwell_entry(entry)
    self.dwell_entry_write_queue.clear()

  def _flush_channel_entry_queue(self):
    if len(self.channel_entry_write_queue) > 0:
      self.logger.log(self.logger.LL_DEBUG, "[sequencer] _flush_channel_entry_queue: num_entries={}".format(len(self.channel_entry_write_queue)))

    for entry in self.channel_entry_write_queue:
      self._send_hw_channel_entry(entry["index"], entry["entry"])
    self.channel_entry_write_queue.clear()

  def _flush_stream_entry_queue(self):
    if len(self.stream_entry_write_queue) > 0:
      self.logger.log(self.logger.LL_DEBUG, "[sequencer] _flush_stream_entry_queue: num_entries={}".format(len(self.stream_entry_write_queue)))

    for entry in self.stream_entry_write_queue:
      self._send_hw_stream_entry(entry["index"], entry["entry"])
    self.stream_entry_write_queue.clear()

  def _send_hw_dwell_entry(self, data):
    self.dwell_entry = data
    key = self.hw_control.send_dwell_entry(data)
    self.hw_dwell_entry_pending.append(key)
    self.logger.log(self.logger.LL_INFO, "[sequencer] sending hw dwell entry: uk={} data={}".format(key, data))

  def _send_hw_channel_entry(self, channel_index, channel_entry):
    self.channel_entries[channel_index] = channel_entry
    key = self.hw_control.send_channel_entry(channel_index, channel_entry)
    self.hw_channel_entry_pending.append(key)
    self.logger.log(self.logger.LL_INFO, "[sequencer] sending hw channel entry: uk={} channel_index={} -> channel_entry={}".format(key, channel_index, channel_entry))

  def _send_hw_stream_entry(self, stream_index, stream_entry):
    self.stream_entries[stream_index] = stream_entry
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
      self.logger.log(self.logger.LL_DEBUG, "[sequencer] pending hw dwell entry acknowledged -- uk={}".format(k))
    return len(keys_found)

  def _check_pending_hw_channel_entries(self):
    keys_found = []
    for k in self.hw_channel_entry_pending:
      if self.hw_interface.hwcp.try_get_result(k) is not None:
        keys_found.append(k)
    for k in keys_found:
      self.hw_channel_entry_pending.remove(k)
      self.logger.log(self.logger.LL_DEBUG, "[sequencer] pending hw channel entry acknowledged -- uk={}".format(k))
    return len(keys_found)

  def _check_pending_hw_stream_entries(self):
    keys_found = []
    for k in self.hw_stream_entry_pending:
      if self.hw_interface.hwcp.try_get_result(k) is not None:
        keys_found.append(k)
    for k in keys_found:
      self.hw_stream_entry_pending.remove(k)
      self.logger.log(self.logger.LL_DEBUG, "[sequencer] pending hw dwell program acknowledged -- uk={}".format(k))
    return len(keys_found)

  def _process_dwell_reports_from_hw(self):
    for packed_report in self.hw_interface.hwdr.output_data_dwell:
      r = self.dwell_reporter.process_message(packed_report)

      if r is None:
        continue

      self.logger.log(self.logger.LL_DEBUG, "[sequencer] _process_dwell_reports_from_hw: full report received, msg_seq_num={} window_seq_num={}".format(r["msg_seq_num"], r["window_seq_num"]))
      self.recorder.log({"dwell_report": r})

      self.hw_stats.submit_report(r)
      self.dwells_to_render.append(r)
      self.threshold_control.process_dwell(r)

    self.hw_interface.hwdr.output_data_dwell.clear()

  def _process_stream_reports_from_hw(self):
    results = []
    for packed_report in self.hw_interface.hwdr.output_data_stream:
      r = self.stream_reporter.process_message(packed_report)

      self.logger.log(self.logger.LL_DEBUG, "[sequencer] _process_stream_reports_from_hw: report received msg_seq_num={} num_samples={}".format(r["msg_seq_num"], len(r["stream_samples"]))) #TODO: reduce logging
      self.recorder.log({"stream_report": r})

      self._track_stream_state(r)
      self.hw_stats.submit_report(r)
      results.append(r)
      #self.analysis_thread.submit_data(r)
      #self.streams_to_render.append(r)
    self.hw_interface.hwdr.output_data_stream.clear()

    #TODO: wait until N items ready (or time elapsed)
    if len(results) > 0:
      #self.logger.log(self.logger.LL_DEBUG, "[sequencer] _process_stream_reports_from_hw: submitting {} items to analysis thread".format(len(results)))
      self.analysis_thread.submit_data(results)

  def _track_stream_state(self, stream_report):
    #self.pr.enable()

    samples = stream_report["stream_samples"]

    trigger_type  = samples["trigger_type"]
    stream_index  = samples["stream_index"]
    channel_index = samples["channel_index"]
    sample_index  = samples["sample_index"]

    # last occurrence of each stream index
    _, first = np.unique(stream_index[::-1], return_index=True)
    last = stream_index.size - 1 - first

    s = stream_index[last]
    self.stream_last_trigger_type[s]  = trigger_type[last]
    self.stream_last_channel_index[s] = channel_index[last]
    self.stream_last_sample_index[s]  = sample_index[last]

  def get_stream_state(self, stream_index):
    return self.stream_last_trigger_type[stream_index], \
           self.stream_last_channel_index[stream_index], \
           self.stream_last_sample_index[stream_index]

  def get_channel_frequency_str(self, channel_index):
    return self.channel_frequency_str[channel_index]

  def _send_initial_hw_control(self):
    self.submit_dwell_entry(pluto_intercept_hw_control.intercept_dwell_control_entry(1, 12345, int(self.dwell_data["frequency"] * 1e3), self.dwell_data["window_duration"]))
    for i in range(INTERCEPT_NUM_CHANNELS):
      self.submit_channel_entry(i, pluto_intercept_hw_control.intercept_channel_control_entry(1, (i == 256), 7, 0, 0xFFFFFFFF, 0xFFFFFFFF, 60000, 0))
    for i in range(INTERCEPT_NUM_STREAMS):
      self.submit_stream_entry(i, pluto_intercept_hw_control.intercept_stream_control_entry(i < (INTERCEPT_NUM_STREAMS - 1), 0xFFFF))

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

  def _update_watchdog(self):
    now = time.time()
    if (self.state == "IDLE") or (self.state == "SIM"):
      return

    if (now - self.last_watchdog_update) > 0.25:
      self.last_watchdog_update = now
      self.hw_interface.enable_hw()

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
        self.hw_interface.set_rx_frequency(self.dwell_data["frequency"])
        self._send_initial_hw_control()

      elif self.state == "INIT_WAIT":
        if (len(self.hw_dwell_entry_pending) == 0) and (len(self.hw_channel_entry_pending) == 0) and (len(self.hw_stream_entry_pending) == 0):
          self.state = "ACTIVE"

      elif self.state == "ACTIVE":
        pass

      elif self.state == "SIM":
        pass

      self._flush_dwell_entry_queue()
      self._flush_channel_entry_queue()
      self._flush_stream_entry_queue()
      self._update_hw_reports()
      self._update_hw_acks()
      self.hw_stats.update()
      self.threshold_control.update()

    self._update_watchdog()

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
