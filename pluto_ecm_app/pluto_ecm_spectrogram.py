import time
from pluto_ecm_hw_pkg import *
import numpy as np
import turbo_colormap

class pluto_ecm_spectrogram:

  def __init__(self, sw_config, dwell_freq, dwell_pane_width, dwell_pane_height_main, dwell_pane_height_trace, scan_results):
    self.sw_config                = sw_config
    self.dwell_freq               = dwell_freq
    self.dwell_pane_width         = dwell_pane_width
    self.dwell_pane_height_main   = dwell_pane_height_main
    self.dwell_pane_height_trace  = dwell_pane_height_trace
    self.scan_results             = scan_results

    self.output_col_width   = int(dwell_pane_width // ECM_NUM_CHANNELS)
    self.output_row_height  = 2 #TODO: config
    self.spec_width         = self.output_col_width * ECM_NUM_CHANNELS
    self.spec_depth_main    = int((dwell_pane_height_main  // self.output_row_height) * self.output_row_height)
    self.spec_depth_trace   = int((dwell_pane_height_trace // self.output_row_height) * self.output_row_height)

    self.spec_main_avg      = np.zeros((self.spec_depth_main, self.spec_width, 3))
    self.spec_main_peak     = np.zeros((self.spec_depth_main, self.spec_width, 3))
    self.spec_main_max_dB   = 60
    self.spec_main_min_dB   = -300

    self.spec_trace         = np.zeros((self.spec_depth_trace, self.spec_width, 3))
    self.spec_trace_max_dB  = 60
    self.spec_trace_min_dB  = -30

    self.colors = {}
    self.colors["trace_peak"] = np.asarray([32, 255, 32])
    self.colors["trace_avg"]  = np.asarray([255, 32, 32])
    self.colors["trace_scan"] = np.asarray([[0, 128, 255], [0, 0, 192], [128, 128, 0], [192, 0, 0]]) #np.asarray([[0, 32, 32], [0, 0, 32], [32, 32, 0], [32, 0, 0]])

  def get_spectrogram(self, peak_not_avg):
    if peak_not_avg:
      return self.spec_main_peak.transpose((1,0,2))
    else:
      return self.spec_main_avg.transpose((1,0,2))

  def get_spectrum_trace(self):
    return self.spec_trace.transpose((1,0,2))

  def _normalize_row(self, data):
    assert (data.shape[0] == data.size)
    data[np.isnan(data)] = 0
    row_max = np.max(data)
    row_scaled = np.divide(data, row_max)
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
  def _shift_and_insert(buf, new_row):
    return np.vstack((new_row, buf[:-1]))

  def process_new_row(self, dwell_buffer):
    scaled_duration = dwell_buffer.dwell_data_by_freq[self.dwell_freq]["channel_duration"][dwell_buffer.dwell_data_last_row_index]
    scaled_duration[scaled_duration == 0] = 1

    input_row_avg   = np.divide(dwell_buffer.dwell_data_by_freq[self.dwell_freq]["channel_accum"][dwell_buffer.dwell_data_last_row_index], scaled_duration)
    input_row_peak  = dwell_buffer.dwell_data_by_freq[self.dwell_freq]["channel_peak"][dwell_buffer.dwell_data_last_row_index].copy()

    buf_avg     = np.zeros(self.spec_width)
    buf_peak    = np.zeros(self.spec_width)
    for input_col in range(ECM_NUM_CHANNELS):
      output_cols = range(int(input_col * self.output_col_width), int((input_col + 1) * self.output_col_width))
      buf_avg[output_cols]  = input_row_avg[input_col]
      buf_peak[output_cols] = input_row_peak[input_col]

    scan_valid = (self.dwell_freq in self.scan_results)
    if scan_valid:
      #result_type = ("iq_power_mean", "iq_power_median", "summary_power_mean", "summary_power_median")
      result_type = ["summary_power_mean"]
      scan_results = self.scan_results[self.dwell_freq]
      buf_scan_dB = np.zeros([len(result_type), self.spec_width])
      for i in range(len(result_type)):
        scan_data = scan_results[result_type[i]]
        for input_col in range(ECM_NUM_CHANNELS):
          output_cols = range(int(input_col * self.output_col_width), int((input_col + 1) * self.output_col_width))
          buf_scan_dB[i, output_cols] = 10*np.log10(scan_data[input_col])

    for i in range(self.output_row_height):
      self.spec_main_avg      = self._shift_and_insert(self.spec_main_avg,  np.expand_dims(turbo_colormap.interpolate_color(self._normalize_row(buf_avg)), 0))
      self.spec_main_peak     = self._shift_and_insert(self.spec_main_peak, np.expand_dims(turbo_colormap.interpolate_color(self._normalize_row(buf_peak)), 0))

    power_floor = 10 ** (self.spec_trace_min_dB / 10)
    buf_avg[buf_avg < power_floor] = power_floor
    buf_peak[buf_peak < power_floor] = power_floor
    buf_avg_dB  = 10*np.log10(buf_avg)
    buf_peak_dB = 10*np.log10(buf_peak)

    self.spec_trace_max_dB = max(np.ceil(np.max(buf_peak_dB) / 10) * 10, self.spec_trace_max_dB)
    vertical_px_per_dB = (self.spec_depth_trace - 4) / (self.spec_trace_max_dB - self.spec_trace_min_dB)

    self.spec_trace = np.zeros((self.spec_depth_trace, self.spec_width, 3))
    trace_x         = np.arange(self.spec_width)
    trace_y_peak    = self.spec_depth_trace - (np.round((buf_peak_dB - self.spec_trace_min_dB) * vertical_px_per_dB).astype(np.uint32) + 2)
    trace_y_avg     = self.spec_depth_trace - (np.round((buf_avg_dB  - self.spec_trace_min_dB) * vertical_px_per_dB).astype(np.uint32) + 2)

    if scan_valid:
      trace_y_m = []
      for i in range(len(result_type)):
        trace_y_m.append(self.spec_depth_trace - (np.round((buf_scan_dB[i] - self.spec_trace_min_dB) * vertical_px_per_dB).astype(np.uint32) + 1))
    else:
      trace_y_m = []

    for i in range(self.output_row_height):
      self.spec_trace[trace_y_peak - 1 + i, trace_x] = self.colors["trace_peak"]
      self.spec_trace[trace_y_avg - 1 + i, trace_x]  = self.colors["trace_avg"]

    for i in range(len(trace_y_m)):
      self.spec_trace[trace_y_m[i], trace_x]  = self.colors["trace_scan"][i]
