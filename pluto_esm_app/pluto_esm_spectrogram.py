import time
from pluto_esm_hw_pkg import *
import numpy as np

class pluto_esm_spectrogram:

  def __init__(self, sw_config, main_spec_dimensions):
    self.sw_config              = sw_config
    self.spec_buffer_main_avg   = np.zeros((main_spec_dimensions[1], main_spec_dimensions[0]))
    self.spec_buffer_main_peak  = np.zeros((main_spec_dimensions[1], main_spec_dimensions[0]))

  def _map_spectrogram_peak(self, input_value, full_scale_value):
    output_value = int(round(255.0 * min(input_value, full_scale_value) / full_scale_value))
    return output_value #(output_value << 16) | (output_value << 8) | output_value

  def get_spectrogram(self, peak_not_avg, output_width, output_height):
    if peak_not_avg:
      return self.spec_buffer_main_peak
    else:
      return self.spec_buffer_main_avg

  def process_new_row(self, dwell_buffer):
    scaled_duration = dwell_buffer.dwell_data_channel_duration[dwell_buffer.dwell_data_last_row_index] * FAST_CLOCK_PERIOD * CHANNELIZER_OVERSAMPLING
    scaled_duration[scaled_duration == 0] = 0
    input_row_avg = np.divide(dwell_buffer.dwell_data_channel_accum[dwell_buffer.dwell_data_last_row_index], scaled_duration)
    #input_row_avg[np.isinf(input_row_avg)] = 0
    input_row_avg[dwell_buffer.dwell_data_channel_center[dwell_buffer.dwell_data_last_row_index]] = 0

    input_row_peak = dwell_buffer.dwell_data_channel_peak[dwell_buffer.dwell_data_last_row_index].copy()
    input_row_peak[dwell_buffer.dwell_data_channel_center[dwell_buffer.dwell_data_last_row_index]] = 0

    buf_avg = np.zeros(self.spec_buffer_main_avg.shape[1])
    buf_peak = np.zeros(self.spec_buffer_main_peak.shape[1])

    width_ratio = dwell_buffer.buffer_width / buf_avg.size
    for output_col in range(buf_avg.size):
      input_cols = range(int(output_col * width_ratio), int((output_col + 1) * width_ratio))
      buf_avg[output_col]  = np.sum(input_row_avg[input_cols])
      buf_peak[output_col] = np.sum(input_row_peak[input_cols])

    self.spec_buffer_main_avg         = np.roll(self.spec_buffer_main_avg, 1, 0)
    self.spec_buffer_main_peak        = np.roll(self.spec_buffer_main_peak, 1, 0)
    self.spec_buffer_main_avg[0, :]   = buf_avg
    self.spec_buffer_main_peak[0, :]  = buf_peak

    #print("avg = {}".format(self.spec_buffer_main_avg[0, :]))
    #print("peak = {}".format(self.spec_buffer_main_peak[0, :]))
