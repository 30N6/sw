import time
import numpy as np
import copy
import traceback

from pluto_intercept_hw_pkg import *

import cProfile, pstats, io
from pstats import SortKey

class pluto_intercept_frequency_estimator:
  def __init__(self, logger, log_dir, config):
    self.logger       = logger
    self.config       = config

    self.fft_width              = 512
    self.fft_window             = np.hanning(self.fft_width)
    self.ffts_to_start_track    = 16384 // self.fft_width # 68 ms

    self.fft_accumulated_power  = np.zeros((INTERCEPT_NUM_STREAMS, self.fft_width))
    self.fft_accumulated_index  = np.zeros(INTERCEPT_NUM_STREAMS, dtype=np.uint32)

    #TODO: config?
    self.num_peaks              = 4

    self.peak_threshold         = 100
    self.peak_max_half_width    = 30
    self.noise_threshold        = 10

    self.est_complete           = np.zeros(INTERCEPT_NUM_STREAMS, dtype=bool)
    self.est_valid              = np.zeros((INTERCEPT_NUM_STREAMS, self.num_peaks), dtype=bool)
    self.est_center             = np.zeros((INTERCEPT_NUM_STREAMS, self.num_peaks))
    self.est_std                = np.zeros((INTERCEPT_NUM_STREAMS, self.num_peaks))
    self.est_accum              = np.zeros((INTERCEPT_NUM_STREAMS, self.num_peaks))

    self.pr = cProfile.Profile()

  def _get_accumulated_peaks(self, stream_index):
    peak_center = np.zeros(self.num_peaks)
    peak_accum  = np.zeros(self.num_peaks)
    peak_std    = np.zeros(self.num_peaks)
    peak_valid  = np.zeros(self.num_peaks, dtype=bool)

    power_data  = self.fft_accumulated_power[stream_index]
    noise_floor = np.median(power_data)
    if noise_floor <= 0:
      return peak_valid, peak_center, peak_std, peak_accum
    power_norm  = power_data / noise_floor

    for i_peak in range(self.num_peaks):
      p = np.argmax(power_norm)
      if (power_norm[p] > self.peak_threshold):
        peak_valid[i_peak] = True

        inclusion_threshold = self.noise_threshold #power_norm[p] * self.peak_power_hyst_factor
        peak_accum_power    = power_norm[p]
        peak_accum_moment_1 = p * power_norm[p]
        peak_accum_moment_2 = p * p * power_norm[p]

        power_norm[p] = 1.0
        upper_done = False
        lower_done = False
        for i_clear in range(1, self.peak_max_half_width):
          upper_index = p + i_clear
          lower_index = p - i_clear

          if (upper_index < power_norm.size) and (power_norm[upper_index] > inclusion_threshold) and not(upper_done):
            peak_accum_power    += power_norm[upper_index]
            peak_accum_moment_1 += upper_index * power_norm[upper_index]
            peak_accum_moment_2 += upper_index * upper_index * power_norm[upper_index]
            power_norm[upper_index] = 1.0
          else:
            upper_done = True

          if (lower_index >= 0) and (power_norm[lower_index] > inclusion_threshold) and not(lower_done):
            peak_accum_power    += power_norm[lower_index]
            peak_accum_moment_1 += lower_index * power_norm[lower_index]
            peak_accum_moment_2 += lower_index * lower_index * power_norm[lower_index]
            power_norm[lower_index] = 1.0
          else:
            lower_done = True

        peak_center[i_peak] = peak_accum_moment_1 / peak_accum_power
        peak_std[i_peak]    = np.sqrt(max(0, (peak_accum_moment_2 / peak_accum_power) - np.square(peak_center[i_peak])))
        peak_accum[i_peak]  = peak_accum_power

      else:
        break

    return peak_valid, peak_center, peak_std, peak_accum

  def stream_buffer_process(self, stream_index, stream_buffer):
    assert (stream_buffer.size % self.fft_width == 0)
    num_ffts_per_buffer = stream_buffer.size // self.fft_width

    assert (self.ffts_to_start_track % num_ffts_per_buffer == 0)
    accumulated_power_ready = False

    if not(self.est_complete[stream_index]):
      for i_fft in range(num_ffts_per_buffer):
        iq_data     = stream_buffer[(self.fft_width * i_fft) : (self.fft_width * (i_fft + 1))]
        iq_windowed = iq_data * self.fft_window
        fft_data    = np.fft.fftshift(np.fft.fft(iq_windowed))
        power_data  = np.square(np.abs(fft_data))

        self.fft_accumulated_power[stream_index] += power_data

        if self.fft_accumulated_index[stream_index] >= (self.ffts_to_start_track - 1):
          accumulated_power_ready = True
          self.fft_accumulated_index[stream_index] = 0
        else:
          self.fft_accumulated_index[stream_index] += 1

      if accumulated_power_ready:
        self.est_complete[stream_index] = True
        assert (self.fft_accumulated_index[stream_index] == 0)
        peak_valid, peak_center, peak_std, peak_accum = self._get_accumulated_peaks(stream_index)

        self.est_valid[stream_index]  = peak_valid
        self.est_center[stream_index] = peak_center / self.fft_width
        self.est_std[stream_index]    = peak_std / self.fft_width
        self.est_accum[stream_index]  = peak_accum

        #self.logger.log(self.logger.LL_INFO, "stream_index={}: power={}".format(stream_index, self.fft_accumulated_power[stream_index]))
        log_line = "[freq_est] stream_buffer_process: estimate complete - stream_index={} valid={} center={} accum={} std={}".format(stream_index, peak_valid, self.est_center[stream_index], self.est_std[stream_index], peak_std)
        self.logger.log(self.logger.LL_INFO, log_line)
        
  def stream_buffer_clear(self, stream_index):
    self.fft_accumulated_power[stream_index] = np.zeros(self.fft_width)
    self.fft_accumulated_index[stream_index] = 0

    self.est_complete[stream_index] = False
    self.est_valid[stream_index]    = np.zeros(self.num_peaks, dtype=bool)
    self.est_center[stream_index]   = np.zeros(self.num_peaks)
    self.est_std[stream_index]      = np.zeros(self.num_peaks)
    self.est_accum[stream_index]    = np.zeros(self.num_peaks)

    self.logger.log(self.logger.LL_INFO, "[freq_est] stream_buffer_clear stream_index={}".format(stream_index))

  def get_estimate(self, stream_index):
    return self.est_valid[stream_index], self.est_center[stream_index], self.est_std[stream_index], self.est_accum[stream_index]
