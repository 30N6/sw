import time
from pluto_esm_hw_pkg import *
import numpy as np
import turbo_colormap

class pluto_esm_spectrogram:

  def __init__(self, sw_config, main_spec_dimensions):
    self.sw_config              = sw_config

    #TODO: take from sw config
    self.output_row_height      = 2
    self.filter_depth           = 16
    self.output_width           = main_spec_dimensions[0]
    self.output_depth           = main_spec_dimensions[1] // self.output_row_height

    self.output_width_trace     = main_spec_dimensions[0]
    self.output_depth_trace     = main_spec_dimensions[1]

    #self.filter_buffer_avg      = np.zeros((self.filter_depth, self.output_width))
    #self.filter_buffer_peak     = np.zeros((self.filter_depth, self.output_width))

    self.spec_main_avg          = np.zeros((self.output_depth, self.output_width, 3))
    self.spec_main_peak         = np.zeros((self.output_depth, self.output_width, 3))
    #self.spec_filt_avg          = np.zeros((self.output_depth, self.output_width, 3))
    #self.spec_filt_peak         = np.zeros((self.output_depth, self.output_width, 3))
    self.last_buffer_avg        = np.zeros(self.output_width)
    self.last_buffer_peak       = np.zeros(self.output_width)

    self.spec_trace             = np.zeros((self.output_depth, self.output_width, 3))
    self.spec_trace_max_dB      = 50
    self.spec_trace_min_dB      = -30

  def get_spectrogram(self, peak_not_avg, main_not_filt):
    if main_not_filt:
      if peak_not_avg:
        return self.spec_main_peak.transpose((1,0,2)).repeat(self.output_row_height, 1)
      else:
        return self.spec_main_avg.transpose((1,0,2)).repeat(self.output_row_height, 1)
    else:
      if peak_not_avg:
        return self.spec_filt_peak.transpose((1,0,2)).repeat(self.output_row_height, 1)
      else:
        return self.spec_filt_avg.transpose((1,0,2)).repeat(self.output_row_height, 1)

  def get_spectrum_trace(self):
    return self.spec_trace.transpose((1,0,2))

  @staticmethod
  def _normalize_row_sqrt(data):
    assert (data.shape[0] == data.size)
    data[np.isnan(data)] = 0
    row_max = np.max(data)
    row_scaled = np.divide(data, row_max)
    return np.sqrt(row_scaled)

  @staticmethod
  def _normalize_row(data):
    assert (data.shape[0] == data.size)
    data[np.isnan(data)] = 0
    row_max = np.max(data)
    return np.divide(data, row_max)

  @staticmethod
  def _shift_and_insert(buf, new_row):
    #buf[1:] = buf[:-1]
    #buf[0] = new_row
    #return buf

    #buf = np.roll(buf, 1, 0)
    #buf[0] = new_row
    #return buf

    return np.vstack((new_row, buf[:-1]))

  @staticmethod
  def _compute_new_filtered_row(new_row, filter_buf):
    row_s = np.sqrt(new_row)
    buf_s = np.sqrt(filter_buf)

    filt_mean = np.mean(buf_s, 0)
    filt_std  = np.std(buf_s, 0)

    r = row_s - filt_mean
    r[r < filt_std] = 0
    return pluto_esm_spectrogram._normalize_row(r)

  def process_new_row(self, dwell_buffer):
    scaled_duration = dwell_buffer.dwell_data_channel_duration[dwell_buffer.dwell_data_last_row_index] #* FAST_CLOCK_PERIOD * CHANNELIZER_OVERSAMPLING
    scaled_duration[scaled_duration == 0] = 1
    input_row_avg = np.divide(dwell_buffer.dwell_data_channel_accum[dwell_buffer.dwell_data_last_row_index], scaled_duration)
    input_row_peak = dwell_buffer.dwell_data_channel_peak[dwell_buffer.dwell_data_last_row_index].copy()

    input_row_avg[dwell_buffer.dwell_data_channel_center[dwell_buffer.dwell_data_last_row_index]] = 0
    input_row_peak[dwell_buffer.dwell_data_channel_center[dwell_buffer.dwell_data_last_row_index]] = 0

    buf_avg = np.zeros(self.output_width)
    buf_peak = np.zeros(self.output_width)

    width_ratio = dwell_buffer.buffer_width / self.output_width
    for output_col in range(self.output_width):
      input_cols = range(int(output_col * width_ratio), int((output_col + 1) * width_ratio))
      buf_avg[output_col]  = np.sum(input_row_avg[input_cols])
      buf_peak[output_col] = np.sum(input_row_peak[input_cols])

    self.spec_main_avg      = self._shift_and_insert(self.spec_main_avg,      np.expand_dims(turbo_colormap.interpolate_color(self._normalize_row_sqrt(buf_avg)), 0))
    self.spec_main_peak     = self._shift_and_insert(self.spec_main_peak,     np.expand_dims(turbo_colormap.interpolate_color(self._normalize_row_sqrt(buf_peak)), 0))

    self.spec_main_avg      = self._shift_and_insert(self.spec_main_avg,      np.expand_dims(turbo_colormap.interpolate_color(self._normalize_row_sqrt(buf_avg)), 0))
    self.spec_main_peak     = self._shift_and_insert(self.spec_main_peak,     np.expand_dims(turbo_colormap.interpolate_color(self._normalize_row_sqrt(buf_peak)), 0))

    self.last_buffer_avg    = buf_avg.copy()
    self.last_buffer_peak   = buf_peak.copy()

    power_floor = 10 ** (self.spec_trace_min_dB / 10)
    buf_avg[buf_avg < power_floor] = power_floor
    buf_peak[buf_peak < power_floor] = power_floor
    buf_avg_dB  = 10*np.log10(buf_avg)
    buf_peak_dB = 10*np.log10(buf_peak)

    self.spec_trace_max_dB = max(np.ceil(np.max(buf_peak_dB) / 10) * 10, self.spec_trace_max_dB)
    vertical_px_per_dB = (self.output_depth_trace - 4) / (self.spec_trace_max_dB - self.spec_trace_min_dB)

    self.spec_trace = np.zeros((self.output_depth_trace, self.output_width_trace, 3))
    trace_x         = np.arange(self.output_width_trace)
    trace_y_peak    = self.output_depth_trace - (np.round((buf_peak_dB - self.spec_trace_min_dB) * vertical_px_per_dB).astype(np.uint32) + 2)
    trace_y_avg     = self.output_depth_trace - (np.round((buf_avg_dB - self.spec_trace_min_dB) * vertical_px_per_dB).astype(np.uint32) + 2)

    for i in range(3):
      self.spec_trace[trace_y_peak - 1 + i, trace_x] = np.asarray([32, 255, 32])
      self.spec_trace[trace_y_avg - 1 + i, trace_x]  = np.asarray([255, 32, 32])

    #self.spec_filt_avg      = self._shift_and_insert(self.spec_filt_avg,      np.expand_dims(turbo_colormap.interpolate_color(self._compute_new_filtered_row(buf_avg, self.filter_buffer_avg)), 0))
    #self.spec_filt_peak     = self._shift_and_insert(self.spec_filt_peak,     np.expand_dims(turbo_colormap.interpolate_color(self._compute_new_filtered_row(buf_peak, self.filter_buffer_peak)), 0))
    #self.filter_buffer_avg  = self._shift_and_insert(self.filter_buffer_avg,  buf_avg)
    #self.filter_buffer_peak = self._shift_and_insert(self.filter_buffer_peak, buf_peak)
