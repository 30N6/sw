from pluto_intercept_hw_pkg import *
import pluto_intercept_hw_control
import numpy as np
import scipy.signal as sp
import time
import copy

class pluto_intercept_trigger_control:
  def __init__(self, logger, sw_config, sequencer):
    self.logger                 = logger
    self.sw_config              = sw_config
    self.sequencer              = sequencer

    self.coast_duration                 = sw_config.trigger_data["coast_duration"]
    self.force_trigger_duration         = sw_config.trigger_data["force_duration"]
    self.force_trigger_stream_index     = INTERCEPT_NUM_STREAMS - 1

    self.threshold_history_len          = sw_config.trigger_data["threshold_history_length"]
    self.threshold_use_max              = bool(sw_config.trigger_data["threshold_use_max_not_mean"])
    self.threshold_update_interval      = sw_config.trigger_data["threshold_update_interval"]
    self.threshold_update_count         = sw_config.trigger_data["threshold_update_count"]
    self.threshold_factor_attack        = sw_config.trigger_data["threshold_factor_attack"]
    self.threshold_factor_retreat       = sw_config.trigger_data["threshold_factor_retreat"]
    self.threshold_update_index         = 0
    self.last_threshold_update_time     = 0

    self.normal_threshold_start         = 10**(sw_config.trigger_data["normal_threshold_start_dB"] / 10)
    self.normal_threshold_continue      = 10**(sw_config.trigger_data["normal_threshold_continue_dB"] / 10)

    self.dwells_received                = 0
    self.channel_data_valid             = False
    self.channel_data_buffer            = np.zeros([INTERCEPT_NUM_CHANNELS, self.threshold_history_len])
    self.channel_data_index             = 0
    self.channel_data_mean              = np.zeros(INTERCEPT_NUM_CHANNELS)
    self.channel_data_filtered          = np.zeros(INTERCEPT_NUM_CHANNELS)

    self.channel_threshold_hw_start     = np.zeros(INTERCEPT_NUM_CHANNELS, dtype=np.uint32)
    self.channel_threshold_hw_continue  = np.zeros(INTERCEPT_NUM_CHANNELS, dtype=np.uint32)

    self.peak_max_count                 = sw_config.trigger_data["forced_peak_count"]
    self.peak_threshold                 = 10**(sw_config.trigger_data["forced_threshold_dB"] / 10)
    self.current_peak_channel           = 0
    self.current_peak_active            = False

    self.render_channel_threshold       = np.zeros(INTERCEPT_NUM_CHANNELS)
    self.render_peaks                   = []

    self.logger.log(self.logger.LL_INFO, "[pluto_intercept_trigger_control] init")

  def _median_filter(self, data, length):
    assert (length % 2 == 1)

    pad_size = length // 2
    padded_data = np.pad(data, pad_size, mode='edge')
    windows = [padded_data[i : i + len(data)] for i in range(length)]

    return np.median(np.column_stack(windows), axis=1)

  def _attack_retreat_filter(self, input_data, output_data, factor_attack, factor_retreat):
    diff = input_data - output_data
    for i in range(input_data.size):
      if diff[i] > 0:
        output_data[i] += factor_attack * diff[i]
      else:
        output_data[i] += factor_retreat * diff[i]

  def process_dwell(self, dwell_report):
    #self.dwell_window_duration = dwell_report["dwell_window_duration"]

    if self.threshold_use_max:
      self.channel_data_buffer[:, self.channel_data_index] = dwell_report["channel_max"]
      threshold_scale = 1/self.threshold_history_len
    else:
      self.channel_data_buffer[:, self.channel_data_index] = dwell_report["channel_accum"]
      threshold_scale = (1/self.threshold_history_len) * (1/dwell_report["dwell_window_duration"])

    self.channel_data_index = (self.channel_data_index + 1) % self.threshold_history_len

    self.channel_data_mean = np.sum(self.channel_data_buffer, 1) * threshold_scale

    if not self.channel_data_valid:
      self.dwells_received += 1
      if self.dwells_received == self.threshold_history_len:
        self.channel_data_valid = True
        self.logger.log(self.logger.LL_INFO, "[pluto_intercept_trigger_control] channel_data_valid=True")
        self.channel_data_filtered = self.channel_data_mean
    else:
      self._attack_retreat_filter(self.channel_data_mean, self.channel_data_filtered, self.threshold_factor_attack, self.threshold_factor_retreat)

    self.channel_threshold_hw_start = (self.channel_data_filtered * self.normal_threshold_start).astype(np.uint32)
    self.channel_threshold_hw_continue = (self.channel_data_filtered * self.normal_threshold_continue).astype(np.uint32)

  def process_stream(self, stream_reports):
    #print(len(stream_reports))
    for report in stream_reports:
      #print(report["stream_samples"])
      #print(report["stream_samples"]["trigger_type"])

      trigger_type  = report["stream_samples"]["trigger_type"]
      stream_index  = report["stream_samples"]["stream_index"]
      channel_index = report["stream_samples"]["channel_index"]
      sample_index  = report["stream_samples"]["sample_index"]

      for i in range(trigger_type.size):
        if (trigger_type[i] == INTERCEPT_STREAM_TRIGGER_TYPE_LAST):
          self.logger.log(self.logger.LL_INFO, "[pluto_intercept_trigger_control] last trigger received: stream={} channel={} sample={}".format(stream_index[i], channel_index[i], sample_index[i]))

        if (trigger_type[i] == INTERCEPT_STREAM_TRIGGER_TYPE_LAST) and (stream_index[i] == self.force_trigger_stream_index):
          print("last trigger received: stream={} channel={}".format(stream_index[i], channel_index[i]))

          if (channel_index[i] != self.current_peak_channel):
            print("channel mismatch: {} {}".format(channel_index[i], self.current_peak_channel))

          assert (channel_index[i] == self.current_peak_channel)

          self.logger.log(self.logger.LL_INFO, "[pluto_intercept_trigger_control] forced trigger complete: channel={}".format(self.current_peak_channel))

          channel_entry = copy.deepcopy(self.sequencer.channel_entries[self.current_peak_channel])
          channel_entry.update_force(0, 0, self.coast_duration)
          self.sequencer.submit_channel_entry(self.current_peak_channel, channel_entry)
          self.current_peak_active = False
          self.current_peak_channel += 1

  def get_thresholds_for_render(self):
    #return self.channel_accum_mean
    if self.channel_data_valid:
      return self.render_channel_threshold
    else:
      return None

  def get_peaks_for_render(self):
    if self.channel_data_valid:
      return self.render_peaks
    else:
      return None

  def update(self):
    now = time.time()

    if not self.channel_data_valid:
      return

    if (now - self.last_threshold_update_time) > self.threshold_update_interval:
      self.last_threshold_update_time = now

      for i in range(self.threshold_update_count):
        if self.threshold_update_index not in self.sequencer.channel_entries:
          continue

        if self.threshold_update_index != self.current_peak_channel:  #avoid potentially restarting the forced trigger
          channel_entry = copy.deepcopy(self.sequencer.channel_entries[self.threshold_update_index])
          channel_entry.update_thresholds(self.channel_threshold_hw_start[self.threshold_update_index], self.channel_threshold_hw_continue[self.threshold_update_index])
          self.sequencer.submit_channel_entry(self.threshold_update_index, channel_entry)

        self.threshold_update_index = (self.threshold_update_index + 1) % INTERCEPT_NUM_CHANNELS

      for i in self.sequencer.channel_entries:
        self.render_channel_threshold[i] = self.sequencer.channel_entries[i].fields["threshold_start"]

      peak_x, _ = sp.find_peaks(self.channel_data_filtered, threshold=self.peak_threshold)
      sort_i = np.argsort(self.channel_data_filtered[peak_x])[::-1]
      peak_x_sorted = peak_x[sort_i]
      #peak_x_sorted = peak_x

      if peak_x_sorted.size > self.peak_max_count:
        peak_x_trimmed = np.sort(peak_x_sorted[0:self.peak_max_count])
      else:
        peak_x_trimmed = np.sort(peak_x_sorted)

      self.render_peaks = peak_x_trimmed
      #print(self.render_peaks)

    if (not self.current_peak_active) and (len(self.render_peaks) > 0):
      idx = np.searchsorted(self.render_peaks, self.current_peak_channel)
      if idx < self.render_peaks.size:
        self.current_peak_channel = self.render_peaks[idx]
      else:
        self.current_peak_channel = self.render_peaks[0]

      if self.current_peak_channel in self.sequencer.channel_entries:
        channel_entry = copy.deepcopy(self.sequencer.channel_entries[self.current_peak_channel])
        channel_entry.update_force(1, self.force_trigger_stream_index, self.force_trigger_duration)

        self.sequencer.submit_channel_entry(self.current_peak_channel, pluto_intercept_hw_control.intercept_channel_control_entry.disabled_entry())
        self.sequencer.submit_channel_entry(self.current_peak_channel, channel_entry)
        self.current_peak_active = True

        self.logger.log(self.logger.LL_INFO, "[pluto_intercept_trigger_control] switching forced trigger: channel={}".format(self.current_peak_channel))
