import time
import numpy as np
import copy
import multiprocessing
import traceback

from pluto_intercept_hw_pkg import *
import pluto_intercept_data_recorder

import cProfile, pstats, io
from pstats import SortKey

class pluto_intercept_analysis_processor:
  def __init__(self, logger, log_dir, config):
    self.logger       = logger
    self.recorder     = pluto_intercept_data_recorder.pluto_intercept_data_recorder(log_dir, "analysis", config["analysis_config"]["enable_analysis_recording"])
    self.config       = config
    self.output_queue = []
    self.input_queue  = []

    self.stream_render_interval   = 0.25
    self.last_stream_render_time  = 0

    self.process_pool             = multiprocessing.Pool(4) #TODO: config
    self.pool_results             = []
    self.pool_timestamp           = []

    # rendering
    self.stream_fft_buffer_depth  = 128
    self.stream_fft_buffer_data   = np.zeros((INTERCEPT_NUM_STREAMS, self.stream_fft_buffer_depth), dtype=np.complex64)
    self.stream_fft_box_height    = 96
    self.stream_fft_trace_max_dB  = 30
    self.stream_fft_trace_min_dB  = -60
    self.stream_fft_color         = np.asarray([32, 255, 32])
    self.stream_fft_filter_factor = 0.9
    self.stream_fft_peak_color    = (np.asarray([255, 32, 32]), np.asarray([32, 32, 255]))
    self.stream_fft_peak_height   = (16, 8)

    # frequency estimation
    self.stream_est_fft_width       = 256
    self.stream_est_fft_window      = np.hanning(self.stream_est_fft_width)
    self.stream_est_sample_interval = 16384 # 68 ms
    self.stream_est_sample_index    = np.zeros(INTERCEPT_NUM_STREAMS, dtype=np.uint32)

    #TODO: config?
    self.stream_est_num_peaks           = 3
    self.stream_est_threshold_floor     = 10
    self.stream_est_threshold_peak      = 100
    self.stream_est_peak_max_width      = 15
    self.stream_est_track_max_dist      = 30
    self.stream_est_track_state_bin     = np.zeros((INTERCEPT_NUM_STREAMS, self.stream_est_num_peaks))
    self.stream_est_track_state_snr     = np.zeros((INTERCEPT_NUM_STREAMS, self.stream_est_num_peaks))
    self.stream_est_track_state_active  = np.zeros((INTERCEPT_NUM_STREAMS, self.stream_est_num_peaks), dtype=np.bool)
    self.stream_est_track_gain_max      = 0.1
    self.stream_est_track_gain_min      = 0.01

    self.stream_channel             = np.zeros(INTERCEPT_NUM_STREAMS, dtype=np.uint32)
    self.stream_buffer_depth        = 4096
    self.stream_buffer_data         = np.zeros((INTERCEPT_NUM_STREAMS, self.stream_buffer_depth), dtype=np.complex64)
    self.stream_buffer_index        = np.zeros(INTERCEPT_NUM_STREAMS, dtype=np.uint32)
    self.stream_buffer_channel      = np.zeros(INTERCEPT_NUM_STREAMS, dtype=np.uint32)

    self.stream_fft_box_data = []
    for i in range(INTERCEPT_NUM_STREAMS):
      self.stream_fft_box_data.append(np.zeros((self.stream_fft_buffer_depth, self.stream_fft_box_height, 3)))

    self.samples_by_index_depth     = 8388608
    #self.samples_by_index           = np.empty((INTERCEPT_NUM_STREAMS, self.samples_by_index_depth), dtype=PACKED_STREAM_SAMPLE_DTYPE)
    self.trigger_type_by_index      = np.empty((INTERCEPT_NUM_STREAMS, self.samples_by_index_depth), dtype=np.uint8)
    self.channel_by_index           = np.empty((INTERCEPT_NUM_STREAMS, self.samples_by_index_depth), dtype=np.uint16)
    self.iq_by_index                = np.empty((INTERCEPT_NUM_STREAMS, self.samples_by_index_depth), dtype=np.complex64)

    assert (self.stream_est_sample_interval % self.stream_buffer_depth == 0)

    self.pr = cProfile.Profile()

  def _process_fft_stream_buffer(self, stream_index, peak_data, track_data):
    stream_power = np.fft.fftshift(np.abs(np.fft.fft(self.stream_fft_buffer_data[stream_index])))
    stream_power[stream_power < 1e-9] = 1e-9

    stream_power_dB = 10*np.log10(stream_power)

    stream_power_dB[stream_power_dB < self.stream_fft_trace_min_dB] = self.stream_fft_trace_min_dB
    stream_power_dB[stream_power_dB > self.stream_fft_trace_max_dB] = self.stream_fft_trace_max_dB

    vertical_px_per_dB = (self.stream_fft_box_height - 4) / (self.stream_fft_trace_max_dB - self.stream_fft_trace_min_dB)

    trace_data = np.zeros((self.stream_fft_buffer_depth, self.stream_fft_box_height, 3))

    combined_peak_data = (peak_data, track_data)
    for i in range(len(combined_peak_data)):
      peak_valid = combined_peak_data[i][0]
      peak_index = combined_peak_data[i][1]
      for i_peak in range(len(peak_valid)):
        if not(peak_valid[i_peak]):
          continue
        peak_x = np.ones(self.stream_fft_peak_height[i], dtype=np.int32) * peak_index[i_peak]
        peak_y = np.arange(self.stream_fft_box_height - self.stream_fft_peak_height[i] - 1, self.stream_fft_box_height - 1)
        for j in range(-1,2):
          adj_x = np.clip(peak_x + j, 0, self.stream_fft_buffer_depth - 1)
          trace_data[adj_x, peak_y] = self.stream_fft_peak_color[i]

      trace_x     = np.arange(self.stream_fft_buffer_depth)
      trace_y     = self.stream_fft_box_height - (np.round((stream_power_dB - self.stream_fft_trace_min_dB) * vertical_px_per_dB).astype(np.uint32) + 2)
      trace_data[trace_x, trace_y] = self.stream_fft_color

    self.stream_fft_box_data[stream_index] = self.stream_fft_filter_factor * self.stream_fft_box_data[stream_index]  + (1 - self.stream_fft_filter_factor) * trace_data

  def _get_stream_power_peaks(self, power_normalized):
    peak_index = np.zeros(self.stream_est_num_peaks, dtype=np.uint32)
    peak_power = np.zeros(self.stream_est_num_peaks)
    peak_valid = np.zeros(self.stream_est_num_peaks, dtype=np.bool)

    power_norm = power_normalized.copy()

    for i_peak in range(self.stream_est_num_peaks):
      p = np.argmax(power_norm)
      if (power_norm[p] > self.stream_est_threshold_peak):
        peak_index[i_peak] = p
        peak_power[i_peak] = power_norm[p]
        peak_valid[i_peak] = True

        upper_done = False
        lower_done = False
        power_norm[p] = 1.0
        for i_clear in range(1, self.stream_est_peak_max_width):
          upper_index = p + i_clear
          lower_index = p - i_clear
          if (upper_index < power_norm.size) and (power_norm[upper_index] > self.stream_est_threshold_floor) and not(upper_done):
            power_norm[upper_index] = 1.0
          else:
            upper_done = True

          if (lower_index >= 0) and (power_norm[lower_index] > self.stream_est_threshold_floor) and not(lower_done):
            power_norm[lower_index] = 1.0
          else:
            lower_done = True

    return peak_valid, peak_index, peak_power

  def _stream_estimate_clear(self, stream_index):
    self.stream_est_track_state_active[stream_index, :] = False
    self.stream_est_track_state_bin[stream_index, :]    = 0
    self.stream_est_track_state_snr[stream_index, :]    = 0

  def _update_stream_tracks(self, stream_index, peak_valid, peak_index, peak_power):
    peak_consumed = np.zeros(self.stream_est_num_peaks, dtype=np.bool)
    track_updated = np.zeros(self.stream_est_num_peaks, dtype=np.bool)

    # for existing valid tracks, find the nearest valid peaks and update the track state
    for i_track in range(self.stream_est_num_peaks):
      if not(self.stream_est_track_state_active[stream_index, i_track]):
        continue

      nearest_valid     = False
      nearest_index     = 0
      nearest_distance  = 0
      for i_peak in range(self.stream_est_num_peaks):
        if not(peak_valid[i_peak]) or peak_consumed[i_peak]:
          continue
        d = abs(peak_index[i_peak] - self.stream_est_track_state_bin[stream_index, i_track])
        if (not(nearest_valid) or (d < nearest_distance)) and (d < self.stream_est_track_max_dist):
          nearest_valid     = True
          nearest_index     = i_peak
          nearest_distance  = d

      if nearest_valid:
        current_peak_snr = peak_power[nearest_index]
        current_peak_index = peak_index[nearest_index]
        peak_consumed[nearest_index] = True
        track_updated[i_track] = True
        update_gain = self.stream_est_track_gain_max * np.min([1.0, current_peak_snr / self.stream_est_track_state_snr[stream_index, i_track]])
        self.stream_est_track_state_bin[stream_index, i_track] = (1 - update_gain) * self.stream_est_track_state_bin[stream_index, i_track] + update_gain * current_peak_index
        self.stream_est_track_state_snr[stream_index, i_track] = (1 - update_gain) * self.stream_est_track_state_snr[stream_index, i_track] + update_gain * current_peak_snr
      else:
        # coasting: if no nearest valid peak exists, decay the tracked SNR
        self.stream_est_track_state_snr[stream_index, i_track] = (1 - self.stream_est_track_gain_min) * self.stream_est_track_state_snr[stream_index, i_track]

    # go through the remaining unassigned detected peaks and try to start new tracks
    sorted_i = np.argsort(peak_power)[::-1]
    remaining_peaks = peak_valid & ~peak_consumed

    remaining_valid = remaining_peaks[sorted_i]
    remaining_index = peak_index[sorted_i]
    remaining_power = peak_power[sorted_i]

    for i_peak in range(self.stream_est_num_peaks):
      if not(remaining_valid[i_peak]):
        continue
      for i_track in range(self.stream_est_num_peaks):
        if self.stream_est_track_state_active[stream_index, i_track]:
          continue
        track_updated[i_track] = True
        self.stream_est_track_state_active[stream_index, i_track] = True
        self.stream_est_track_state_bin[stream_index, i_track]    = remaining_index[i_peak]
        self.stream_est_track_state_snr[stream_index, i_track]    = remaining_power[i_peak]
        break

    # drop tracks which have coasted/decayed too long
    for i_track in range(self.stream_est_num_peaks):
      if not(self.stream_est_track_state_active[stream_index, i_track]):
        continue
      if track_updated[i_track]:
        continue
      if (self.stream_est_track_state_snr[stream_index, i_track] < self.stream_est_threshold_peak):
        self.stream_est_track_state_active[stream_index, i_track] = False
        self.stream_est_track_state_bin[stream_index, i_track]    = 0
        self.stream_est_track_state_snr[stream_index, i_track]    = 0

  def _process_stream_estimate(self, stream_index):
    iq_data     = self.stream_buffer_data[stream_index, 0:self.stream_est_fft_width]
    iq_windowed = iq_data * self.stream_est_fft_window
    fft_data    = np.fft.fftshift(np.fft.fft(iq_windowed))
    power_data  = np.square(np.abs(fft_data))

    power_normalized = power_data / np.median(power_data)

    peak_valid, peak_index, peak_power = self._get_stream_power_peaks(power_normalized)

    self._update_stream_tracks(stream_index, peak_valid, peak_index, peak_power)

    peak_index_for_stream_box   = (peak_index                                    * self.stream_fft_buffer_depth / self.stream_est_fft_width).astype(np.uint32)
    track_index_for_stream_box  = (self.stream_est_track_state_bin[stream_index] * self.stream_fft_buffer_depth / self.stream_est_fft_width).astype(np.uint32)
    track_valid = self.stream_est_track_state_active[stream_index]

    self.stream_fft_buffer_data[stream_index] = self.stream_buffer_data[stream_index, 0:self.stream_fft_buffer_depth]
    self._process_fft_stream_buffer(stream_index, (peak_valid, peak_index_for_stream_box), (track_valid, track_index_for_stream_box))

  def _process_stream_buffer(self, stream_index):
    #print("{} : _process_stream_buffer index={}".format(time.time(), stream_index))

    if self.stream_est_sample_index[stream_index] == 0:
      self._process_stream_estimate(stream_index) #update the frequency estimate and the rendered spectrum trace -- only using partial data

    #TODO: downconvert buffer - using full data
    #TODO: will use stream_buffer_channel here

    self.stream_est_sample_index[stream_index] = (self.stream_est_sample_index[stream_index] + self.stream_buffer_depth) % self.stream_est_sample_interval

  def _process_input_queue(self):
    t_start = time.time()
    if len(self.input_queue) == 0:
      return

    total_samples = 0
    for entry in self.input_queue:
      total_samples += entry["stream_samples"].size

    print("{} : _process_input_queue start - len={} total_samples={}".format(time.time(), len(self.input_queue), total_samples))

    #samples      = np.concatenate([e["stream_samples"] for e in self.input_queue])
    channel_index = np.concatenate([e["stream_samples"]["channel_index"] for e in self.input_queue])
    trigger_type  = np.concatenate([e["stream_samples"]["trigger_type"]  for e in self.input_queue])
    stream_index  = np.concatenate([e["stream_samples"]["stream_index"]  for e in self.input_queue])
    iq            = np.concatenate([e["stream_IQ"]                       for e in self.input_queue])

    total_samples_by_index = np.zeros(INTERCEPT_NUM_STREAMS, dtype=np.uint32)

    for s in range(INTERCEPT_NUM_STREAMS):
      stream_mask = (stream_index == s)
      num_samples = int(stream_mask.sum())
      total_samples_by_index[s] = num_samples
      if num_samples:
        self.trigger_type_by_index[s, 0:num_samples]  = trigger_type[stream_mask]
        self.channel_by_index[s, 0:num_samples]       = channel_index[stream_mask]
        self.iq_by_index[s, 0:num_samples]            = iq[stream_mask]

    for s in range(INTERCEPT_NUM_STREAMS):
      num_samples = total_samples_by_index[s]
      if num_samples == 0:
        continue

      stream_iq       = self.iq_by_index[s, 0:num_samples]
      stream_trigger  = self.trigger_type_by_index[s, 0:num_samples]
      stream_channel  = self.channel_by_index[s, 0:num_samples]
      stream_depth    = self.stream_buffer_depth
      stream_buf      = self.stream_buffer_data[s]
      stream_idx      = self.stream_buffer_index[s]

      # LAST positions; each segment includes its LAST sample
      last_idx = np.flatnonzero(stream_trigger == INTERCEPT_STREAM_TRIGGER_TYPE_LAST)
      bounds = np.concatenate(([0], last_idx + 1, [num_samples]))

      for start, end in zip(bounds[:-1], bounds[1:]):
        seg = stream_iq[start:end]
        pos = 0
        while pos < len(seg):
          space = stream_depth - stream_idx
          take = min(space, len(seg) - pos)
          stream_buf[stream_idx:(stream_idx + take)] = seg[pos:(pos + take)]
          stream_idx += take
          pos += take
          if stream_idx == stream_depth:
            self.stream_buffer_index[s] = 0
            self.stream_buffer_channel[s] = stream_channel[start]
            self._process_stream_buffer(s)
            stream_idx = 0

        # segment ended on a LAST
        if (end > start) and (end <= num_samples) and (stream_trigger[end - 1] == INTERCEPT_STREAM_TRIGGER_TYPE_LAST):
          self._stream_estimate_clear(s)

      self.stream_buffer_index[s] = stream_idx

    self.input_queue.clear()

    now = time.time()
    print("{} : _process_input_queue done, time={}".format(now, now - t_start))

  def _update_output(self):
    now = time.time()

    if (now - self.last_stream_render_time) > self.stream_render_interval:
      self.last_stream_render_time = now
      #print("{} : fft_box_data updated".format(now))

      self.output_queue.append({"stream_fft_box_data": self.stream_fft_box_data})

  def get_output_data(self):
    return self.output_queue

  def submit_data(self, data):
    if "stream_samples" not in data:
      self.logger.log(self.logger.LL_INFO, "[pluto_intercept_analysis_processor]: error: data={}".format(data))
      self.logger.flush()

    assert("stream_samples" in data)
    self.input_queue.append(data)

  def update(self):
    #self.pr.enable()

    self._process_input_queue()
    self._update_output()

    #self.pr.disable()
    #s = io.StringIO()
    #sortby = SortKey.CUMULATIVE
    #ps = pstats.Stats(self.pr, stream=s).sort_stats(sortby)
    #ps.print_stats()
    #print(s.getvalue())

  def shutdown(self, reason):
    self.logger.log(self.logger.LL_INFO, "[pluto_intercept_analysis_processor]: shutdown started - reason={}".format(reason))
    self.recorder.shutdown(reason)
    self.logger.log(self.logger.LL_INFO, "[pluto_intercept_analysis_processor]: shutdown complete")
    self.logger.flush()
