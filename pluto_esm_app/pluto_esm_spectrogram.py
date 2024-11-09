import pygame
import time
from pluto_esm_hw_pkg import *
import numpy as np
import math

class pluto_esm_spectrogram:

  def __init__(self, sw_config, sequencer):
    self.sequencer            = sequencer
    self.max_freq             = sw_config.max_freq
    self.dwell_bw             = sw_config.config["dwell_config"]["freq_step"]
    self.adjusted_max_freq    = self.max_freq + self.dwell_bw / 2

    self.num_channels     = ESM_NUM_CHANNELS_NARROW
    self.channel_spacing  = (ADC_CLOCK_FREQUENCY / self.num_channels) / 1e6
    assert (self.channel_spacing == sw_config.config["dwell_config"]["channel_step"])

    num_columns = int(round(self.adjusted_max_freq / self.channel_spacing))
    num_rows    = 256 #config?

    self.dwell_data_channel_accum     = np.zeros((num_rows, num_columns), dtype=np.uint64)
    self.dwell_data_channel_peak      = np.zeros((num_rows, num_columns), dtype=np.uint32)
    self.dwell_data_channel_duration  = np.zeros((num_rows, num_columns), dtype=np.uint32)
    self.dwell_data_start_time        = np.zeros(num_rows, dtype=np.uint64)
    self.dwell_data_row_index         = 0

    self.spectrogram_peak             = np.zeros((num_rows, num_columns), dtype=np.uint32)
    self.spectrogram_avg              = np.zeros((num_rows, num_columns), dtype=np.uint32)

    center_channel = self.num_channels // 2
    self.channel_range = [center_channel - int(round(0.5 * self.dwell_bw / self.channel_spacing)),
                          center_channel + int(round(0.5 * self.dwell_bw / self.channel_spacing))]

  def _map_spectrogram_peak(self, input_value, full_scale_value):
    output_value = int(round(255.0 * min(input_value, full_scale_value) / full_scale_value))
    return output_value #(output_value << 16) | (output_value << 8) | output_value

  def _process_dwell_updates(self):
    while len(self.sequencer.dwells_to_render) > 0:
      entry         = self.sequencer.dwells_to_render.pop(0)
      dwell_data    = entry["dwell_data"]
      dwell_report  = entry["dwell_report"]
      is_first      = entry["first_in_sequence"]
      is_last       = entry["last_in_sequence"]

      assert (dwell_report["num_channels"] == self.num_channels)
      assert (len(dwell_report["channel_data"]) == self.num_channels)
      #assert (dwell_report["frequency"] == dwell_data.frequency) #TODO: update

      if is_first:
        self.dwell_data_channel_accum[self.dwell_data_row_index, :]     = 0
        self.dwell_data_channel_peak[self.dwell_data_row_index, :]      = 0
        self.dwell_data_channel_duration[self.dwell_data_row_index, :]  = 0
        self.dwell_data_start_time[self.dwell_data_row_index]           = dwell_report["ts_dwell_start"]

      center_channel_index = int(round(dwell_data.frequency / self.channel_spacing))
      center_offset = self.num_channels // 2

      channels = []

      for i in range(self.channel_range[0], self.channel_range[1] + 1):
        entry = dwell_report["channel_data"][i]
        assert (entry["index"] == i)

        global_channel_index = center_channel_index + (i - center_offset)
        channels.append(global_channel_index)

        self.dwell_data_channel_accum[self.dwell_data_row_index, global_channel_index]     += entry["accum"]
        self.dwell_data_channel_peak[self.dwell_data_row_index, global_channel_index]      = max(self.dwell_data_channel_peak[self.dwell_data_row_index, global_channel_index], entry["max"])
        self.dwell_data_channel_duration[self.dwell_data_row_index, global_channel_index]  += dwell_report["num_samples"]

        self.spectrogram_peak[self.dwell_data_row_index, global_channel_index] = self._map_spectrogram_peak(self.dwell_data_channel_peak[self.dwell_data_row_index, global_channel_index], 100)
        #self.spectrogram_avg[self.dwell_data_row_index, global_channel_index] = self._map_spectrogram_peak(
        #  self.dwell_data_channel_accum[self.dwell_data_row_index, global_channel_index] / self.dwell_data_channel_duration[self.dwell_data_row_index, global_channel_index], 0.01)
        self.spectrogram_avg[self.dwell_data_row_index, global_channel_index] = self._map_spectrogram_peak(
          self.dwell_data_channel_accum[self.dwell_data_row_index, global_channel_index], 100)

      print("dwell: freq={} first={} last={} chan_index={}".format(dwell_data.frequency, is_first, is_last, center_channel_index))
      print("channels = {}".format(channels))
      #print(self.dwell_data_channel_accum[self.dwell_data_row_index, :])

      if is_last:
        self.dwell_data_row_index = (self.dwell_data_row_index + 1) % self.dwell_data_channel_accum.shape[0]

  def update(self):
    self._process_dwell_updates()

