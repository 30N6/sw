import time
from pluto_ecm_hw_pkg import *
import numpy as np
import turbo_colormap

class pluto_ecm_spectrogram:

  def __init__(self, sw_config, dwell_freq, dwell_pane_width, dwell_pane_height_main, dwell_pane_height_trace, dwell_trigger_thresholds, program_tag_to_state):
    self.sw_config                = sw_config
    self.dwell_freq               = dwell_freq
    self.dwell_pane_width         = dwell_pane_width
    self.dwell_pane_height_main   = dwell_pane_height_main
    self.dwell_pane_height_trace  = dwell_pane_height_trace
    self.dwell_trigger_thresholds = dwell_trigger_thresholds
    self.program_tag_to_state     = program_tag_to_state

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
    self.colors["trace_peak"]   = np.asarray([32, 255, 32])
    self.colors["trace_avg"]    = np.asarray([255, 32, 32])
    self.colors["trace_thresh"] = np.asarray([0, 128, 255])
    self.colors["state_colors"] = {"IDLE": np.asarray([0, 0, 0]), "SCAN": np.asarray([0, 32, 128]), "TX_LISTEN": np.asarray([0, 128, 32]), "TX_ACTIVE": np.asarray([255, 192, 32])}
    self.colors["tx_active"]    = np.asarray([255, 0, 0])

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
  def _shift_and_insert(buf, new_row):
    return np.vstack((new_row, buf[:-1]))

  def process_new_row(self, dwell_buffer):
    dwell_data = dwell_buffer.dwell_data_by_freq[self.dwell_freq]

    scaled_duration = dwell_data["channel_duration"][dwell_buffer.dwell_data_last_row_index]
    scaled_duration[scaled_duration == 0] = 1

    input_row_avg       = np.divide(dwell_data["channel_accum"][dwell_buffer.dwell_data_last_row_index], scaled_duration)
    input_row_peak      = dwell_data["channel_peak"][dwell_buffer.dwell_data_last_row_index].copy()
    input_row_thresh    = self.dwell_trigger_thresholds[self.dwell_freq]
    input_row_tag       = dwell_data["program_tag"][dwell_buffer.dwell_data_last_row_index]
    input_row_tx_active = dwell_data["tx_active"][dwell_buffer.dwell_data_last_row_index]

    state_color = self.colors["state_colors"][self.program_tag_to_state[input_row_tag]]

    buf_avg     = np.zeros(self.spec_width)
    buf_peak    = np.zeros(self.spec_width)
    buf_thresh  = np.zeros(self.spec_width)
    for input_col in range(ECM_NUM_CHANNELS):
      output_cols = range(int(input_col * self.output_col_width), int((input_col + 1) * self.output_col_width))
      buf_avg[output_cols]    = input_row_avg[input_col]
      buf_peak[output_cols]   = input_row_peak[input_col]
      buf_thresh[output_cols] = input_row_thresh[input_col]

    for i in range(self.output_row_height):
      self.spec_main_avg      = self._shift_and_insert(self.spec_main_avg,  np.expand_dims(turbo_colormap.interpolate_color(self._normalize_row(buf_avg)), 0))
      self.spec_main_peak     = self._shift_and_insert(self.spec_main_peak, np.expand_dims(turbo_colormap.interpolate_color(self._normalize_row(buf_peak)), 0))

      self.spec_main_avg[0, 0:self.output_col_width, :]   = state_color
      self.spec_main_peak[0, 0:self.output_col_width, :]  = state_color

      if input_row_tx_active:
        self.spec_main_avg[0, -self.output_col_width:-1, :]   = self.colors["tx_active"]
        self.spec_main_peak[0, -self.output_col_width:-1, :]  = self.colors["tx_active"]

    power_floor = 10 ** (self.spec_trace_min_dB / 10)
    power_ceil  = 10 ** (self.spec_trace_max_dB / 10)

    buf_avg[buf_avg < power_floor]        = power_floor
    buf_peak[buf_peak < power_floor]      = power_floor
    buf_thresh[buf_thresh < power_floor]  = power_floor
    buf_avg[buf_avg > power_ceil]         = power_ceil
    buf_peak[buf_peak > power_ceil]       = power_ceil
    buf_thresh[buf_thresh > power_ceil]   = power_ceil

    buf_avg_dB    = 10*np.log10(buf_avg)
    buf_peak_dB   = 10*np.log10(buf_peak)
    buf_thresh_dB = 10*np.log10(buf_thresh)

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
