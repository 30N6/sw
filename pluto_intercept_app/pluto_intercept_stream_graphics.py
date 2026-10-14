import time
import numpy as np
import copy
import traceback

from pluto_intercept_hw_pkg import *

class pluto_intercept_stream_graphics:
  def __init__(self, logger, config):
    self.logger = logger
    self.config = config

    # rendering
    self.stream_fft_buffer_depth  = 128
    self.stream_fft_buffer_data   = np.zeros((INTERCEPT_NUM_STREAMS, self.stream_fft_buffer_depth), dtype=np.complex64)
    self.stream_fft_box_height    = 96
    self.stream_fft_trace_max_dB  = 30
    self.stream_fft_trace_min_dB  = -60
    self.stream_fft_color         = np.asarray([32, 255, 32])
    self.stream_fft_filter_factor = 0.9
    self.stream_fft_peak_color    = np.asarray([255, 32, 32])
    self.stream_fft_peak_height   = 16

    self.stream_fft_box_data = []
    for i in range(INTERCEPT_NUM_STREAMS):
      self.stream_fft_box_data.append(np.zeros((self.stream_fft_buffer_depth, self.stream_fft_box_height, 3)))

  def _process_fft_stream_buffer(self, stream_index, peak_data):
    stream_power = np.fft.fftshift(np.abs(np.fft.fft(self.stream_fft_buffer_data[stream_index])))
    stream_power[stream_power < 1e-9] = 1e-9

    stream_power_dB = 10*np.log10(stream_power)

    stream_power_dB[stream_power_dB < self.stream_fft_trace_min_dB] = self.stream_fft_trace_min_dB
    stream_power_dB[stream_power_dB > self.stream_fft_trace_max_dB] = self.stream_fft_trace_max_dB

    vertical_px_per_dB = (self.stream_fft_box_height - 4) / (self.stream_fft_trace_max_dB - self.stream_fft_trace_min_dB)

    trace_data = np.zeros((self.stream_fft_buffer_depth, self.stream_fft_box_height, 3))

    peak_valid = peak_data[0]
    peak_index = peak_data[1]
    for i_peak in range(len(peak_valid)):
      if not(peak_valid[i_peak]):
        continue
      peak_x = np.ones(self.stream_fft_peak_height, dtype=np.int32) * peak_index[i_peak]
      peak_y = np.arange(self.stream_fft_box_height - self.stream_fft_peak_height - 1, self.stream_fft_box_height - 1)
      for j in range(-1,2):
        adj_x = np.clip(peak_x + j, 0, self.stream_fft_buffer_depth - 1)
        trace_data[adj_x, peak_y] = self.stream_fft_peak_color

    trace_x = np.arange(self.stream_fft_buffer_depth)
    trace_y = self.stream_fft_box_height - (np.round((stream_power_dB - self.stream_fft_trace_min_dB) * vertical_px_per_dB).astype(np.uint32) + 2)
    trace_data[trace_x, trace_y] = self.stream_fft_color

    self.stream_fft_box_data[stream_index] = self.stream_fft_filter_factor * self.stream_fft_box_data[stream_index]  + (1 - self.stream_fft_filter_factor) * trace_data

  def _stream_buffer_process(self, stream_index, stream_buffer, est_valid, est_center):
    est_center_for_stream_box = (est_center * self.stream_fft_buffer_depth).astype(np.uint32)
    self.stream_fft_buffer_data[stream_index] = stream_buffer[0:self.stream_fft_buffer_depth]
    self._process_fft_stream_buffer(stream_index, (est_valid, est_center_for_stream_box))

  def get_stream_box_data(self):
    return self.stream_fft_box_data