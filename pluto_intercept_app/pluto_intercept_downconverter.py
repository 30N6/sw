import time
import numpy as np
import copy
import traceback

from pluto_intercept_hw_pkg import *

import cProfile, pstats, io
from pstats import SortKey

class pluto_intercept_decimator:
  def __init__(self, ratio, num_taps, cutoff, fs, beta):
    self.R = int(ratio)
    self.h = self._get_lpf_coefficients(num_taps, cutoff, fs, beta)
    self.L = len(self.h)
    self.h_rev = self.h[::-1].copy()          # matches np.convolve
    self.history = np.zeros(self.L - 1, dtype=np.complex64)

  def _get_lpf_coefficients(self, num_taps, cutoff, fs, beta):
    assert(num_taps % self.R == 0)
    n = np.arange(num_taps) - (num_taps - 1) / 2
    h = 2 * cutoff / fs * np.sinc(2 * cutoff / fs * n)
    h *= np.kaiser(num_taps, beta)
    h /= np.sum(h)
    return h.astype(np.float32)

  def process(self, x):
    x = np.asarray(x, dtype=np.complex64)
    if x.size == 0:
      return np.empty(0, dtype=np.complex64)

    data = np.concatenate((self.history, x))
    n_valid = len(data) - self.L + 1
    n_out = max(0, n_valid // self.R)

    if n_out == 0:
      self.history = data[-(self.L - 1):].copy()
      return np.empty(0, dtype=np.complex64)

    # windows starting at 0, R, 2R, ...
    starts = np.arange(n_out) * self.R
    windows = np.lib.stride_tricks.sliding_window_view(data, self.L)[starts]
    y = (windows @ self.h_rev).astype(np.complex64)

    # always retain the last L-1 samples for the next call
    self.history = data[-(self.L - 1):].copy()
    return y

  def reset(self):
    self.history = np.zeros(self.L - 1, dtype=np.complex64)

class pluto_intercept_downconverter:
  def __init__(self, logger, config):
    self.logger               = logger
    self.config               = config

    self.downconversion_ratio = 6
    self.fs_output            = CHANNELIZER_OUTPUT_FREQUENCY / self.downconversion_ratio

    self.input_buffer_depth   = 6 * 4096

    self.input_buffer         = np.zeros((INTERCEPT_NUM_STREAMS, self.input_buffer_depth), dtype=np.complex64)
    self.input_count          = np.zeros(INTERCEPT_NUM_STREAMS, dtype=np.uint32)

    self.num_converters         = 4
    self.lo_active              = np.zeros((INTERCEPT_NUM_STREAMS, self.num_converters), dtype=bool)
    self.lo_phase               = np.zeros((INTERCEPT_NUM_STREAMS, self.num_converters), dtype=np.uint32)
    self.lo_frequency           = np.zeros((INTERCEPT_NUM_STREAMS, self.num_converters))
    self.lo_time_range          = np.arange(self.input_buffer_depth) * CHANNELIZER_OUTPUT_PERIOD

    self.filters                = [[pluto_intercept_decimator(self.downconversion_ratio, 72, 16e3, CHANNELIZER_OUTPUT_FREQUENCY, 6.0) for i in range(self.num_converters)] for j in range(INTERCEPT_NUM_STREAMS)]

    self.pr = cProfile.Profile()

  def update_downconverters(self, stream_index, est_valid, est_center):
    for i_lo in range(self.num_converters):
      if self.lo_active[stream_index, i_lo] or not(est_valid[i_lo]):
        continue

      self.lo_active[stream_index, i_lo] = True
      self.lo_frequency[stream_index, i_lo] = (0.5 - est_center[i_lo]) * CHANNELIZER_OUTPUT_FREQUENCY
      self.logger.log(self.logger.LL_INFO, "[downconv]: update_downconverters: stream_index={} lo_index={} --> freq={:.1f}".format(stream_index, i_lo, self.lo_frequency[stream_index, i_lo] * 1e-3))

  def stream_buffer_process(self, stream_index, stream_buffer):
    assert (self.input_buffer_depth % stream_buffer.size == 0)

    write_index = self.input_count[stream_index]
    self.input_buffer[stream_index, write_index:(write_index + stream_buffer.size)] = stream_buffer
    self.input_count[stream_index] += stream_buffer.size

    results = [None for i in range(self.num_converters)]

    if self.input_count[stream_index] >= self.input_buffer_depth:
      self.input_count[stream_index] = 0

      for i_lo in range(self.num_converters):
        if not(self.lo_active[stream_index, i_lo]):
          continue

        lo_t    = self.lo_phase[stream_index, i_lo] * CHANNELIZER_OUTPUT_PERIOD + self.lo_time_range
        lo_data = np.exp(1j * 2 * np.pi * self.lo_frequency[stream_index, i_lo] * lo_t).astype(np.complex64)
        self.lo_phase[stream_index, i_lo] += self.input_buffer_depth

        iq_shifted      = self.input_buffer[stream_index] * lo_data
        iq_downsampled  = self.filters[stream_index][i_lo].process(iq_shifted)
        results[i_lo]   = {"lo_index": i_lo, "lo_frequency": self.lo_frequency[stream_index, i_lo], "iq_data": iq_downsampled, "fs": self.fs_output}

    return results

  def stream_buffer_clear(self, stream_index):
    self.input_buffer[stream_index] = np.zeros(self.input_buffer_depth, dtype=np.complex64)
    self.input_count[stream_index]  = 0
    self.lo_active[stream_index]    = np.zeros(self.num_converters, dtype=bool)
    self.lo_phase[stream_index]     = np.zeros(self.num_converters, dtype=np.uint32)
    self.lo_frequency[stream_index] = np.zeros(self.num_converters)

    for i_filter in range(self.num_converters):
      self.filters[stream_index][i_filter].reset()

