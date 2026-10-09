import time
from pluto_intercept_hw_pkg import *
import numpy as np
import turbo_colormap

class pluto_intercept_spectrogram:

  def __init__(self, dwell_pane_width, dwell_pane_height_waterfall, dwell_pane_height_trace):
    self.dwell_pane_width             = dwell_pane_width
    self.dwell_pane_height_waterfall  = dwell_pane_height_waterfall
    self.dwell_pane_height_trace      = dwell_pane_height_trace

    self.channel_threshold      = np.zeros(INTERCEPT_NUM_CHANNELS)

    self.output_col_width       = int(dwell_pane_width // INTERCEPT_NUM_CHANNELS)
    self.output_row_height      = 2 #TODO: config
    self.spec_width             = self.output_col_width * INTERCEPT_NUM_CHANNELS
    self.spec_depth_waterfall   = int((dwell_pane_height_waterfall  // self.output_row_height) * self.output_row_height)
    self.spec_depth_trace       = int((dwell_pane_height_trace      // self.output_row_height) * self.output_row_height)

    self.spec_waterfall_avg     = np.zeros((self.spec_depth_waterfall, self.spec_width, 3), np.uint8)
    self.spec_waterfall_peak    = np.zeros((self.spec_depth_waterfall, self.spec_width, 3), np.uint8)
    self.spec_waterfall_max_dB  = 60
    self.spec_waterfall_min_dB  = -300

    self.spec_trace             = np.zeros((self.spec_depth_trace, self.spec_width, 3))
    self.spec_trace_max_dB      = 100
    self.spec_trace_min_dB      = 30

    self.colors = {}
    self.colors["trace_peak"]   = np.asarray([32, 255, 32], dtype=np.uint8)
    self.colors["trace_avg"]    = np.asarray([255, 32, 32], dtype=np.uint8)
    self.colors["trace_thresh"] = np.asarray([0, 128, 255], dtype=np.uint8)

  def set_thresholds(self, thresholds):
    self.channel_threshold = thresholds

  def get_waterfall(self, peak_not_avg):
    if peak_not_avg:
      return self.spec_waterfall_peak.transpose((1,0,2))
    else:
      return self.spec_waterfall_avg.transpose((1,0,2))

  def get_trace(self):
    return self.spec_trace.transpose((1,0,2))

  def _normalize_row(self, data):
    assert (data.shape[0] == data.size)
    data[np.isnan(data)] = 0
    row_max = np.max(data)
    if row_max != 0:
      row_scaled = np.divide(data, row_max)
    else:
      row_scaled = data
    return np.sqrt(row_scaled)

    #assert (data.shape[0] == data.size)
    #data[np.isnan(data)] = 0
    #data[data > 10**(self.spec_main_max_dB/10)] = 10**(self.spec_main_max_dB/10)
    #data[data < 10**(self.spec_main_min_dB/10)] = 10**(self.spec_main_min_dB/10)
    #
    #row_dB = 10*np.log10(data)
    #row_scaled = (row_dB - self.spec_main_min_dB) / (self.spec_main_max_dB - self.spec_main_min_dB)
    #return row_scaled

  @staticmethod
  def _shift_and_insert(buf, new_row, n):
    buf[n:] = buf[:-n]
    buf[:n] = new_row

  def process_new_dwell(self, dwell_data):
    input_row_avg     = np.divide(dwell_data["channel_accum"], dwell_data["dwell_window_duration"])
    input_row_peak    = dwell_data["channel_max"].copy()
    input_row_thresh  = self.channel_threshold

    row_avg  = turbo_colormap.interpolate_color(self._normalize_row(input_row_avg))
    row_peak = turbo_colormap.interpolate_color(self._normalize_row(input_row_peak))
    self._shift_and_insert(self.spec_waterfall_avg, row_avg, self.output_row_height)
    self._shift_and_insert(self.spec_waterfall_peak, row_peak, self.output_row_height)

    power_floor = 10 ** (self.spec_trace_min_dB / 10)
    power_ceil  = 10 ** (self.spec_trace_max_dB / 10)

    input_row_avg[input_row_avg < power_floor]        = power_floor
    input_row_peak[input_row_peak < power_floor]      = power_floor
    input_row_thresh[input_row_thresh < power_floor]  = power_floor
    input_row_avg[input_row_avg > power_ceil]         = power_ceil
    input_row_peak[input_row_peak > power_ceil]       = power_ceil
    input_row_thresh[input_row_thresh > power_ceil]   = power_ceil

    buf_avg_dB    = 10*np.log10(input_row_avg)
    buf_peak_dB   = 10*np.log10(input_row_peak)
    buf_thresh_dB = 10*np.log10(input_row_thresh)

    self.spec_trace_max_dB = max(np.ceil(np.max(buf_peak_dB) / 10) * 10, self.spec_trace_max_dB)
    vertical_px_per_dB = (self.spec_depth_trace - 4) / (self.spec_trace_max_dB - self.spec_trace_min_dB)

    self.spec_trace = np.zeros((self.spec_depth_trace, self.spec_width, 3))
    trace_x         = np.arange(self.spec_width)
    trace_y_peak    = self.spec_depth_trace - (np.round((buf_peak_dB    - self.spec_trace_min_dB) * vertical_px_per_dB).astype(np.uint32) + 2)
    trace_y_avg     = self.spec_depth_trace - (np.round((buf_avg_dB     - self.spec_trace_min_dB) * vertical_px_per_dB).astype(np.uint32) + 2)
    trace_y_thresh  = self.spec_depth_trace - (np.round((buf_thresh_dB  - self.spec_trace_min_dB) * vertical_px_per_dB).astype(np.uint32) + 2)

    for i in range(self.output_row_height):
      self.spec_trace[trace_y_peak - 1 + i, trace_x] = self.colors["trace_peak"]
      self.spec_trace[trace_y_avg - 1 + i, trace_x]  = self.colors["trace_avg"]

    self.spec_trace[trace_y_thresh, trace_x]  = self.colors["trace_thresh"]
