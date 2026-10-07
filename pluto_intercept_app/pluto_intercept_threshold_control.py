from pluto_intercept_hw_pkg import *
import numpy as np
import time
import copy

class pluto_intercept_threshold_control:
  def __init__(self, logger, sw_config, sequencer):
    self.logger                 = logger
    self.sw_config              = sw_config
    self.sequencer              = sequencer

    self.threshold_history_len  = 16  #TODO: config
    self.threshold_window_len   = 5
    self.threshold_scale        = 3.0
    self.threshold_use_max      = True
    self.threshold_scale_full   = 0
    self.threshold_continue_fac = 0.5 #TODO config

    assert (self.threshold_window_len % 2 == 1)

    self.dwells_received        = 0
    self.threshold_valid        = False

    #self.dwell_window_duration  = 0
    self.channel_data_buffer            = np.zeros([INTERCEPT_NUM_CHANNELS, self.threshold_history_len])
    self.channel_data_index             = 0
    self.channel_data_mean              = np.zeros(INTERCEPT_NUM_CHANNELS)
    self.channel_threshold_raw          = np.zeros(INTERCEPT_NUM_CHANNELS)
    self.channel_threshold_hw_start     = np.zeros(INTERCEPT_NUM_CHANNELS, dtype=np.uint32)
    self.channel_threshold_hw_continue  = np.zeros(INTERCEPT_NUM_CHANNELS, dtype=np.uint32)
    self.channel_threshold_render       = np.zeros(INTERCEPT_NUM_CHANNELS)

    self.threshold_update_interval  = 0.125 #TODO: config
    self.threshold_update_count     = 32  #TODO: config
    self.threshold_update_index     = 0
    self.last_threshold_update_time = 0

    self.logger.log(self.logger.LL_INFO, "[pluto_intercept_threshold_control] init")

  def _median_filter(self, data, length):
    assert (length % 2 == 1)

    pad_size = length // 2
    padded_data = np.pad(data, pad_size, mode='edge')
    windows = [padded_data[i : i + len(data)] for i in range(length)]

    return np.median(np.column_stack(windows), axis=1)

  def process_dwell(self, dwell_report):
    #self.dwell_window_duration = dwell_report["dwell_window_duration"]

    if self.threshold_use_max:
      self.channel_data_buffer[:, self.channel_data_index] = dwell_report["channel_max"]
      self.threshold_scale_full = (1/self.threshold_history_len) * self.threshold_scale
    else:
      self.channel_data_buffer[:, self.channel_data_index] = dwell_report["channel_accum"]
      self.threshold_scale_full = (1/self.threshold_history_len) * self.threshold_scale / dwell_report["dwell_window_duration"]

    self.channel_data_index = (self.channel_data_index + 1) % self.threshold_history_len

    self.channel_data_mean = np.sum(self.channel_data_buffer, 1) * self.threshold_scale_full
    self.channel_threshold_raw = self._median_filter(self.channel_data_mean, self.threshold_window_len)

    ##print(dwell_report["channel_max"])
    ##print(dwell_report["channel_accum"])
    #for i in range(len(self.channel_threshold_raw)):
    #  print(i)
    #  print(self.channel_threshold_raw[i])
    #  print(self.channel_threshold_raw[i].astype(np.uint32))
    #
    self.channel_threshold_hw_start = self.channel_threshold_raw.astype(np.uint32)
    self.channel_threshold_hw_continue = (self.channel_threshold_raw * self.threshold_continue_fac).astype(np.uint32)

    if not self.threshold_valid:
      self.dwells_received += 1
      if self.dwells_received == self.threshold_history_len:
        self.threshold_valid = True
        self.logger.log(self.logger.LL_INFO, "[pluto_intercept_threshold_control] threshold_valid=True")

  def get_thresholds_for_render(self):
    #return self.channel_accum_mean
    if self.threshold_valid:
      return self.channel_threshold_render
    else:
      return None

  def update(self):
    now = time.time()

    if not self.threshold_valid:
      return

    if (now - self.last_threshold_update_time) > self.threshold_update_interval:
      self.last_threshold_update_time = now

      for i in range(self.threshold_update_count):
        if self.threshold_update_index not in self.sequencer.channel_entries:
          continue
        channel_entry = copy.copy(self.sequencer.channel_entries[self.threshold_update_index])
        channel_entry.update_thresholds(self.channel_threshold_hw_start[self.threshold_update_index], self.channel_threshold_hw_continue[self.threshold_update_index])
        self.sequencer.submit_channel_entry(self.threshold_update_index, channel_entry)

        self.threshold_update_index = (self.threshold_update_index + 1) % INTERCEPT_NUM_CHANNELS

      for i in self.sequencer.channel_entries:
        self.channel_threshold_render[i] = self.sequencer.channel_entries[i].fields["threshold_start"]

