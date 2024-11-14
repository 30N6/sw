from pluto_esm_hw_pkg import *
import numpy as np

class pluto_esm_dwell_stats_buffer:

  def __init__(self, sw_config):
    self.max_freq             = sw_config.max_freq
    self.dwell_bw             = sw_config.config["dwell_config"]["freq_step"]

    self.num_channels     = ESM_NUM_CHANNELS_NARROW
    self.channel_spacing  = (ADC_CLOCK_FREQUENCY / self.num_channels) / 1e6
    assert (self.channel_spacing == sw_config.config["dwell_config"]["channel_step"])

    self.buffer_width        = int(round(self.max_freq / self.channel_spacing)) + 1
    self.buffer_depth        = 1024 #config?

    self.dwell_data_channel_accum     = np.zeros((self.buffer_depth, self.buffer_width), dtype=np.uint64)
    self.dwell_data_channel_peak      = np.zeros((self.buffer_depth, self.buffer_width), dtype=np.uint32)
    self.dwell_data_channel_duration  = np.zeros((self.buffer_depth, self.buffer_width), dtype=np.uint32)
    self.dwell_data_channel_center    = np.zeros((self.buffer_depth, self.buffer_width), dtype=bool)
    self.dwell_data_start_time        = np.zeros(self.buffer_depth, dtype=np.uint64)
    self.dwell_data_row_index         = 0
    self.dwell_data_last_row_index    = 0

    self.dwell_channel_info           = {}

    center_channel = self.num_channels // 2
    self.channel_range = [center_channel - int(round(0.5 * self.dwell_bw / self.channel_spacing)),
                          center_channel + int(round(0.5 * self.dwell_bw / self.channel_spacing))]

  def process_dwell_update(self, dwell_entry):
    dwell_data    = dwell_entry["dwell_data"]
    dwell_report  = dwell_entry["dwell_report"]
    is_first      = dwell_entry["first_in_sequence"]
    is_last       = dwell_entry["last_in_sequence"]

    assert (dwell_report["num_channels"] == self.num_channels)
    assert (len(dwell_report["channel_data"]) == self.num_channels)
    #assert (dwell_report["frequency"] == dwell_data.frequency) #TODO: update

    if is_first:
      self.dwell_data_channel_accum[self.dwell_data_row_index, :]     = 0
      self.dwell_data_channel_peak[self.dwell_data_row_index, :]      = 0
      self.dwell_data_channel_duration[self.dwell_data_row_index, :]  = 0
      self.dwell_data_channel_center[self.dwell_data_row_index, :]    = False
      self.dwell_data_start_time[self.dwell_data_row_index]           = dwell_report["ts_dwell_start"]

    center_channel_index = int(round(dwell_data.frequency / self.channel_spacing))
    center_offset = self.num_channels // 2

    #channels = []

    self.dwell_data_channel_center[self.dwell_data_row_index, center_channel_index - 1] = True

    if dwell_data.frequency not in self.dwell_channel_info:
      self.dwell_channel_info[dwell_data.frequency] = {"center": center_channel_index,
                                                       "start":  center_channel_index + self.channel_range[0] - center_offset,
                                                       "stop":   center_channel_index + self.channel_range[1] - center_offset}

    for i in range(self.channel_range[0], self.channel_range[1] + 1):
      entry = dwell_report["channel_data"][i]
      assert (entry["index"] == i)

      global_channel_index = center_channel_index + (i - center_offset)
      #channels.append(global_channel_index)

      self.dwell_data_channel_accum[self.dwell_data_row_index, global_channel_index]     += entry["accum"]
      self.dwell_data_channel_peak[self.dwell_data_row_index, global_channel_index]      = max(self.dwell_data_channel_peak[self.dwell_data_row_index, global_channel_index], entry["max"])
      self.dwell_data_channel_duration[self.dwell_data_row_index, global_channel_index]  += dwell_report["num_samples"]

    #print("dwell: freq={} first={} last={} chan_index={}".format(dwell_data.frequency, is_first, is_last, center_channel_index))
    #print("channels = {}".format(channels))
    #print(self.channel_range)
    #print(self.dwell_data_channel_accum[self.dwell_data_row_index, :])

    if is_last:
      self.dwell_data_last_row_index = self.dwell_data_row_index
      self.dwell_data_row_index = (self.dwell_data_row_index + 1) % self.dwell_data_channel_accum.shape[0]

    return is_last

