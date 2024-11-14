from pluto_esm_hw_pkg import *
import numpy as np

class pluto_esm_dwell_threshold:

  def __init__(self, logger, sw_config, dwell_freqs):
    self.max_freq             = sw_config.max_freq
    self.dwell_bw             = sw_config.config["dwell_config"]["freq_step"]

    self.num_channels     = ESM_NUM_CHANNELS_NARROW
    self.channel_spacing  = (ADC_CLOCK_FREQUENCY / self.num_channels) / 1e6
    assert (self.channel_spacing == sw_config.config["dwell_config"]["channel_step"])

    self.buffer_width         = int(round(self.max_freq / self.channel_spacing)) + 1
    self.buffer_depth         = 128

    self.channel_buffer_avg   = np.zeros((self.buffer_depth, self.buffer_width))
    self.channel_buffer_peak  = np.zeros((self.buffer_depth, self.buffer_width))
    self.channel_buffer_valid = np.zeros(self.buffer_depth, dtype=bool)
    self.channel_buffer_index = 0

    self.dwell_freqs          = dwell_freqs
    self.dwell_threshold      = {}

    self.threshold_SNR        = 4 #TODO: config? dynamic based on pulse count?

  def process_new_dwell_row(self, dwell_buffer):
    input_row_duration = dwell_buffer.dwell_data_channel_duration[dwell_buffer.dwell_data_last_row_index].copy()
    input_row_duration[input_row_duration == 0] = 1

    input_row_avg = np.divide(dwell_buffer.dwell_data_channel_accum[dwell_buffer.dwell_data_last_row_index], input_row_duration)
    input_row_avg[dwell_buffer.dwell_data_channel_center[dwell_buffer.dwell_data_last_row_index]] = 0

    input_row_peak = dwell_buffer.dwell_data_channel_peak[dwell_buffer.dwell_data_last_row_index].copy()
    input_row_peak[dwell_buffer.dwell_data_channel_center[dwell_buffer.dwell_data_last_row_index]] = 0

    self.channel_buffer_avg[self.channel_buffer_index]    = input_row_avg
    self.channel_buffer_peak[self.channel_buffer_index]   = input_row_peak
    self.channel_buffer_valid[self.channel_buffer_index]  = True

    for freq in self.dwell_freqs:
      if freq not in dwell_buffer.dwell_channel_info:
        continue
      #print("dwell_channel_info[{}] = {}".format(freq, dwell_buffer.dwell_channel_info[freq]))
      channel_info = dwell_buffer.dwell_channel_info[freq]

      da_1        = dwell_buffer.dwell_data_channel_accum[dwell_buffer.dwell_data_last_row_index][channel_info["start"] : (channel_info["stop"] + 1)]
      dwell_avg   = input_row_avg[channel_info["start"] : (channel_info["stop"] + 1)]
      dwell_peak  = input_row_peak[channel_info["start"] : (channel_info["stop"] + 1)]

      #print("da_1[{}] = {}".format(freq, da_1))
      #print("dwell_avg[{}] = {}".format(freq, dwell_avg))
      #print("dwell_peak[{}] = {}".format(freq, dwell_peak))
      print("mean_peak[{}] = {:.1f} std={:.1f}".format(freq, np.mean(dwell_peak), np.std(dwell_peak)))

      #center_channel_index = int(round(freq / self.channel_spacing))

      #dwell_index_range = [


    self.channel_buffer_index = (self.channel_buffer_index + 1) % self.buffer_depth