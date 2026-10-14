import time
import numpy as np
import copy
import multiprocessing
import traceback

from pluto_intercept_hw_pkg import *
import pluto_intercept_data_recorder
import pluto_intercept_frequency_estimator
import pluto_intercept_downconverter
import pluto_intercept_stream_graphics

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

    self.stream_channel             = np.zeros(INTERCEPT_NUM_STREAMS, dtype=np.uint32)
    self.stream_buffer_depth        = 4096
    self.stream_buffer_data         = np.zeros((INTERCEPT_NUM_STREAMS, self.stream_buffer_depth), dtype=np.complex64)
    self.stream_buffer_index        = np.zeros(INTERCEPT_NUM_STREAMS, dtype=np.uint32)
    self.stream_buffer_channel      = np.zeros(INTERCEPT_NUM_STREAMS, dtype=np.uint32)

    self.samples_by_index_depth     = 8388608
    self.trigger_type_by_index      = np.empty((INTERCEPT_NUM_STREAMS, self.samples_by_index_depth), dtype=np.uint8)
    self.channel_by_index           = np.empty((INTERCEPT_NUM_STREAMS, self.samples_by_index_depth), dtype=np.uint16)
    self.iq_by_index                = np.empty((INTERCEPT_NUM_STREAMS, self.samples_by_index_depth), dtype=np.complex64)
    #self.samples_by_index           = np.empty((INTERCEPT_NUM_STREAMS, self.samples_by_index_depth), dtype=PACKED_STREAM_SAMPLE_DTYPE)

    self.stream_graphics            = pluto_intercept_stream_graphics.pluto_intercept_stream_graphics(logger, config)
    self.stream_freq_estimator      = pluto_intercept_frequency_estimator.pluto_intercept_frequency_estimator(logger, self.recorder, config)
    self.stream_downconverter       = pluto_intercept_downconverter.pluto_intercept_downconverter(logger, config)

    self.downconverted_output_queue = []

    self.pr = cProfile.Profile()

  def _stream_buffer_process(self, stream_index):
    #print("{} : _stream_buffer_process index={}".format(time.time(), stream_index))
    current_stream_buffer = self.stream_buffer_data[stream_index]

    #TODO
    self.stream_freq_estimator.stream_buffer_process(stream_index, current_stream_buffer)
    est_valid, est_center, est_std, est_accum = self.stream_freq_estimator.get_estimate(stream_index)

    self.stream_graphics._stream_buffer_process(stream_index, current_stream_buffer, est_valid, est_center)

    self.stream_downconverter.update_downconverters(stream_index, est_valid, est_center)
    downconverted_data = self.stream_downconverter.stream_buffer_process(stream_index, current_stream_buffer)


    #self.logger.log(self.logger.LL_INFO, "[processor]: _stream_buffer_process: stream_index={} est_valid={} est_center={}".format(stream_index, est_valid, est_center))
    #self.logger.flush()

    now = time.time()
    for i in range(len(downconverted_data)):
      if downconverted_data[i] is None:
        continue

      #data_uI = self.stream_downconverter.input_buffer[stream_index].real.tolist()
      #data_uQ = self.stream_downconverter.input_buffer[stream_index].imag.tolist()
      #data_dI = downconverted_data[i].real.tolist()
      #data_dQ = downconverted_data[i].imag.tolist()
      #lo_freq = self.stream_downconverter.lo_frequency[stream_index, i]
      #
      ##self.logger.log(self.logger.LL_INFO, "[processor]: _stream_buffer_process: stream_index={} downconverted_data[{}]={}".format(stream_index, i, downconverted_data[i].size))
      #self.recorder.log({"type": "downconversion", "stream_index": stream_index, "channel_index": int(self.stream_buffer_channel[stream_index]), "lo_index": i, "lo_freq": lo_freq, "data_uI": data_uI, "data_uQ": data_uQ, "data_dI": data_dI, "data_dQ": data_dQ})

      output_entry = {"stream_index"  : stream_index,
                      "channel_index" : self.stream_buffer_channel[stream_index],
                      "timestamp"     : now,
                      "lo_index"      : downconverted_data[i][0],
                      "lo_frequency"  : downconverted_data[i][1],
                      "iq_data"       : downconverted_data[i][2]}

      #print(output_entry)

      #self.downconverted_output_queue.push_back(output_entry)

  def _stream_buffer_clear(self, stream_index):
    self.stream_freq_estimator.stream_buffer_clear(stream_index)
    self.stream_downconverter.stream_buffer_clear(stream_index)

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
            self._stream_buffer_process(s)
            stream_idx = 0

        # segment ended on a LAST
        if (end > start) and (end <= num_samples) and (stream_trigger[end - 1] == INTERCEPT_STREAM_TRIGGER_TYPE_LAST):
          self._stream_buffer_clear(s)

      self.stream_buffer_index[s] = stream_idx

    self.input_queue.clear()

    now = time.time()
    print("{} : _process_input_queue done, time={}".format(now, now - t_start))

  def _update_output(self):
    now = time.time()

    if (now - self.last_stream_render_time) > self.stream_render_interval:
      self.last_stream_render_time = now
      #print("{} : fft_box_data updated".format(now))
      self.output_queue.append({"stream_fft_box_data": self.stream_graphics.get_stream_box_data()})

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
