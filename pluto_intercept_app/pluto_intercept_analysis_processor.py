import time
import numpy as np
import copy
import multiprocessing
import traceback

from pluto_intercept_hw_pkg import *
import pluto_intercept_data_recorder

class pluto_intercept_analysis_processor:
  def __init__(self, logger, log_dir, config, output_queue):
    self.logger       = logger
    self.recorder     = pluto_intercept_data_recorder.pluto_intercept_data_recorder(log_dir, "analysis", config["analysis_config"]["enable_analysis_recording"])
    self.config       = config
    self.output_queue = output_queue
    self.input_queue  = []

    self.stream_render_interval   = 0.25
    self.last_stream_render_time  = 0

    self.process_pool             = multiprocessing.Pool(4) #TODO: config
    self.pool_results             = []
    self.pool_timestamp           = []

    self.stream_fft_buffer_depth  = 128
    self.stream_fft_buffer_data   = np.zeros((INTERCEPT_NUM_STREAMS, self.stream_fft_buffer_depth), dtype=np.complex64)
    self.stream_fft_buffer_index  = np.zeros(INTERCEPT_NUM_STREAMS, dtype=np.uint32)
    self.stream_fft_channel_index = np.zeros(INTERCEPT_NUM_STREAMS, dtype=np.uint32)
    self.stream_fft_box_height    = 96
    self.stream_fft_trace_max_dB  = 30
    self.stream_fft_trace_min_dB  = -60
    self.stream_fft_color         = np.asarray([32, 255, 32])
    self.stream_fft_filter_factor = 0.9

    self.stream_fft_box_data = []
    for i in range(INTERCEPT_NUM_STREAMS):
      self.stream_fft_box_data.append(np.zeros((self.stream_fft_buffer_depth, self.stream_fft_box_height, 3)))

  def _process_fft_stream_buffer(self, stream_index):
    stream_power = np.fft.fftshift(np.abs(np.fft.fft(self.stream_fft_buffer_data[stream_index])))
    stream_power[stream_power < 1e-9] = 1e-9

    stream_power_dB = 10*np.log10(stream_power)

    stream_power_dB[stream_power_dB < self.stream_fft_trace_min_dB] = self.stream_fft_trace_min_dB
    stream_power_dB[stream_power_dB > self.stream_fft_trace_max_dB] = self.stream_fft_trace_max_dB

    vertical_px_per_dB = (self.stream_fft_box_height - 4) / (self.stream_fft_trace_max_dB - self.stream_fft_trace_min_dB)

    trace_data  = np.zeros((self.stream_fft_buffer_depth, self.stream_fft_box_height, 3))
    trace_x     = np.arange(self.stream_fft_buffer_depth)
    trace_y     = self.stream_fft_box_height - (np.round((stream_power_dB - self.stream_fft_trace_min_dB) * vertical_px_per_dB).astype(np.uint32) + 2)

    trace_data[trace_x, trace_y] = self.stream_fft_color

    self.stream_fft_box_data[stream_index] = self.stream_fft_filter_factor * self.stream_fft_box_data[stream_index]  + (1 - self.stream_fft_filter_factor) * trace_data


  def _process_input_queue(self):
    for entry in self.input_queue:
      samples = entry["stream_samples"]

      stream_index  = samples["stream_index"]
      channel_index = samples["channel_index"]
      iq            = (samples["I"] + 1j * samples["Q"]) * CHANNELIZER_SCALE_FACTOR

      for i in range(stream_index.size):
        s = stream_index[i]

        if self.stream_fft_channel_index[s] != channel_index[i]:
          self.stream_fft_channel_index[s]  = channel_index[i]
          self.stream_fft_buffer_index[s]   = 0
          self.stream_fft_box_data[s]       = np.zeros((self.stream_fft_buffer_depth, self.stream_fft_box_height, 3))

        self.stream_fft_buffer_data[s, self.stream_fft_buffer_index[s]] = iq[i]

        if (self.stream_fft_buffer_index[s] == (self.stream_fft_buffer_depth - 1)):
          self._process_fft_stream_buffer(s)
        self.stream_fft_buffer_index[s] = (self.stream_fft_buffer_index[s] + 1) % self.stream_fft_buffer_depth

    self.input_queue.clear()

  def _update_output(self):
    now = time.time()

    if (now - self.last_stream_render_time) > self.stream_render_interval:
      self.last_stream_render_time = now

      self.output_queue.put({"stream_fft_box_data": self.stream_fft_box_data})

  def submit_data(self, data):
    if "stream_samples" not in data:
      self.logger.log(self.logger.LL_INFO, "[pluto_intercept_analysis_processor]: error: data={}".format(data))
      self.logger.flush()
    assert("stream_samples" in data)
    self.input_queue.append(data)

  def update(self):
    self._process_input_queue()
    self._update_output()

  def shutdown(self, reason):
    self.logger.log(self.logger.LL_INFO, "[pluto_intercept_analysis_processor]: shutdown started - reason={}".format(reason))
    self.recorder.shutdown(reason)
    self.logger.log(self.logger.LL_INFO, "[pluto_intercept_analysis_processor]: shutdown complete")
    self.logger.flush()
