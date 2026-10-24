import time
import numpy as np
import copy
import multiprocessing
import traceback

from pluto_intercept_hw_pkg import *
import pluto_intercept_data_recorder
import pluto_intercept_stream_graphics
import pluto_intercept_frequency_estimator
import pluto_intercept_downconverter
import pluto_intercept_signal_analysis
import pluto_intercept_signal_tracker

import cProfile, pstats, io
from pstats import SortKey

class pluto_intercept_analysis_processor:
  def __init__(self, logger, log_dir, sw_config):
    self.logger       = logger
    self.recorder     = pluto_intercept_data_recorder.pluto_intercept_data_recorder(log_dir, "analysis", sw_config.config["analysis"]["enable_recording"])
    self.config       = sw_config
    self.output_queue = []
    self.input_queue  = []

    self.stream_render_interval   = 0.25
    self.last_stream_render_time  = 0
    self.signal_render_interval   = 0.05
    self.last_signal_render_time  = 0

    self.process_pool             = multiprocessing.Pool(4) #TODO: config
    self.pool_results             = []
    self.pool_timestamp           = []

    self.stream_channel             = np.zeros(INTERCEPT_NUM_STREAMS, dtype=np.uint32)
    self.stream_buffer_depth        = 4096
    self.stream_buffer_data         = np.zeros((INTERCEPT_NUM_STREAMS, self.stream_buffer_depth), dtype=np.complex64)
    self.stream_buffer_index        = np.zeros(INTERCEPT_NUM_STREAMS, dtype=np.uint32)
    self.stream_buffer_channel      = np.zeros(INTERCEPT_NUM_STREAMS, dtype=np.uint32)
    self.stream_buffer_dwell_freq   = np.zeros(INTERCEPT_NUM_STREAMS, dtype=np.uint32)

    self.samples_by_index_depth     = 8388608
    self.trigger_type_by_index      = np.empty((INTERCEPT_NUM_STREAMS, self.samples_by_index_depth), dtype=np.uint8)
    self.channel_by_index           = np.empty((INTERCEPT_NUM_STREAMS, self.samples_by_index_depth), dtype=np.uint16)
    self.iq_by_index                = np.empty((INTERCEPT_NUM_STREAMS, self.samples_by_index_depth), dtype=np.complex64)
    #self.samples_by_index           = np.empty((INTERCEPT_NUM_STREAMS, self.samples_by_index_depth), dtype=PACKED_STREAM_SAMPLE_DTYPE)

    self.stream_graphics            = pluto_intercept_stream_graphics.pluto_intercept_stream_graphics(logger, sw_config.config)
    self.stream_freq_estimator      = pluto_intercept_frequency_estimator.pluto_intercept_frequency_estimator(logger, self.recorder, sw_config.config)
    self.stream_downconverter       = pluto_intercept_downconverter.pluto_intercept_downconverter(logger, sw_config.config)
    self.signal_analysis            = pluto_intercept_signal_analysis.pluto_intercept_signal_analysis(sw_config.config)
    self.signal_tracker             = pluto_intercept_signal_tracker.pluto_intercept_signal_tracker(logger, sw_config.config, sw_config.frequency_db)

    self.downconverted_output_queue = []

    self.pr = cProfile.Profile()

  @staticmethod
  def _convert_numpy_for_json(obj):
    if isinstance(obj, np.integer):
      return int(obj)
    if isinstance(obj, np.floating):
      return float(obj)
    if isinstance(obj, np.ndarray):
      r = obj.tolist()
      if isinstance(r[0], np.floating):
        return [float(item) for item in r]
      if isinstance(r[0], np.integer):
        return [int(item) for item in r]
      return r
    if isinstance(obj, dict):
      for key in obj:
        obj[key] = pluto_intercept_analysis_processor._convert_numpy_for_json(obj[key])
      return obj
    return obj

  @staticmethod
  def _get_center_frequency(dwell_frequency, channel_index, lo_frequency):
    channel_offset = (channel_index - (INTERCEPT_NUM_CHANNELS / 2)) * (ADC_CLOCK_FREQUENCY * 1e-6 / INTERCEPT_NUM_CHANNELS)
    return dwell_frequency + channel_offset + lo_frequency * 1e-6

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

      output_entry = {"timestamp_conv_end"  : now,
                      "stream_index"        : stream_index,
                      "channel_index"       : self.stream_buffer_channel[stream_index],
                      "dwell_frequency"     : self.stream_buffer_dwell_freq[stream_index],
                      "center_frequency"    : self._get_center_frequency(self.stream_buffer_dwell_freq[stream_index], self.stream_buffer_channel[stream_index], downconverted_data[i]["lo_frequency"]),
                      "lo_index"            : downconverted_data[i]["lo_index"],
                      "lo_frequency"        : downconverted_data[i]["lo_frequency"],
                      "iq_data"             : downconverted_data[i]["iq_data"],
                      "fs"                  : downconverted_data[i]["fs"]}

      self.downconverted_output_queue.append(output_entry)

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

    #print("{} : _process_input_queue start - len={} total_samples={}".format(time.time(), len(self.input_queue), total_samples))

    #samples        = np.concatenate([e["stream_samples"] for e in self.input_queue])
    channel_index   = np.concatenate([e["stream_samples"]["channel_index"] for e in self.input_queue])
    trigger_type    = np.concatenate([e["stream_samples"]["trigger_type"]  for e in self.input_queue])
    stream_index    = np.concatenate([e["stream_samples"]["stream_index"]  for e in self.input_queue])
    iq              = np.concatenate([e["stream_IQ"]                       for e in self.input_queue])
    dwell_frequency = self.input_queue[0]["dwell_frequency"]

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
            self.stream_buffer_index[s]       = 0
            self.stream_buffer_channel[s]     = stream_channel[start]
            self.stream_buffer_dwell_freq[s]  = dwell_frequency
            self._stream_buffer_process(s)
            stream_idx = 0

        # segment ended on a LAST
        if (end > start) and (end <= num_samples) and (stream_trigger[end - 1] == INTERCEPT_STREAM_TRIGGER_TYPE_LAST):
          self._stream_buffer_clear(s)

      self.stream_buffer_index[s] = stream_idx

    self.input_queue.clear()

    now = time.time()
    #print("{} : _process_input_queue done, time={}".format(now, now - t_start))

  def _process_downconverted_queue(self):
    now = time.time()

    for entry in self.downconverted_output_queue:
      try:
        result = self.process_pool.apply_async(self.signal_analysis.compute_features, (entry,))
        self.pool_results.append(result)
        self.pool_timestamp.append(now)
      except Exception as e:
        self.logger.log(self.logger.LL_WARN, "_process_downconverted_queue: exception: {}".format(e))
        self.logger.log(self.logger.LL_WARN, "_process_downconverted_queue: traceback: {}".format(traceback.format_exc()))
        self.logger.flush()

    self.downconverted_output_queue.clear()

  def _process_pool_results(self):
    while len(self.pool_results) > 0:
      if not self.pool_results[0].ready():
        break

      result          = self.pool_results.pop(0).get()
      ts_queue_start  = self.pool_timestamp.pop(0)

      #if "sw_timestamp" not in result:
      #  print("result: {}".format(result))

      now = time.time()

      self._log_pool_result(result)

      #print("_process_pool_results: {:.6f} {:.6f} {:.6f} f={}".format(now - result["timestamp_conv_end"], now - ts_queue_start, result["timestamp_proc_end"] - result["timestamp_proc_start"], result["center_frequency"]))
      result.pop("iq_data_I")
      result.pop("iq_data_Q")

      self.signal_tracker.submit_analysis_report(result)


      #self.signal_tracker.submit_analysis_report(result)
      #self.signal_processing_delay = now - result["sw_timestamp"]
      #
      #self.logger.log(self.logger.LL_INFO, "_process_pool_results: full processing delay: {:.3f}  from submission delay: {:.3f} processing_time: {:.3f} time_since_read:{:.3f}".format(self.signal_processing_delay, now - self.pool_timestamp[0], result["processing_time"], result["time_since_read"]))
      #
      #result_for_logging = result.copy()
      #result_for_logging["analysis"] = result["analysis"].copy()
      #result_for_logging["analysis"].pop("iq_stft_abs")
      #result_for_logging["analysis"].pop("ofdm_data")
      #self.recorder.log(result_for_logging)

  def _log_pool_result(self, result):
    converted_result = self._convert_numpy_for_json(result)
    #print(converted_result)
    self.recorder.log({"signal_analysis": converted_result})

  def _shutdown_pool(self):
    self.logger.log(self.logger.LL_INFO, "_shutdown_pool: {} items in queue".format(len(self.pool_results)))

    while len(self.pool_results) > 0:
      if not self.pool_results[0].ready():
        self.logger.log(self.logger.LL_INFO, "_shutdown_pool: waiting for result...")
        time.sleep(0.1)
        continue
      result = self.pool_results[0].get()
      self.logger.log(self.logger.LL_INFO, "_shutdown_pool: result done, {} remaining".format(len(self.pool_results) - 1))

      self.pool_results.pop(0)
      self.pool_timestamp.pop(0)

  def _update_output(self):
    now = time.time()

    if (now - self.last_stream_render_time) > self.stream_render_interval:
      self.last_stream_render_time = now
      self.output_queue.append({"stream_fft_box_data": self.stream_graphics.get_stream_box_data()})

    if (now - self.last_signal_render_time) > self.signal_render_interval:
      self.last_signal_render_time = now
      self.output_queue.append({"tracked_signals": self.signal_tracker.get_tracked_signals()})


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
    self._process_downconverted_queue()
    self._process_pool_results()
    self._update_output()
    self.signal_tracker.update()

    #self.pr.disable()
    #s = io.StringIO()
    #sortby = SortKey.CUMULATIVE
    #ps = pstats.Stats(self.pr, stream=s).sort_stats(sortby)
    #ps.print_stats()
    #print(s.getvalue())

  def shutdown(self, reason):
    self.logger.log(self.logger.LL_INFO, "[pluto_intercept_analysis_processor]: shutdown started - reason={}".format(reason))
    self._shutdown_pool()
    self.process_pool.terminate()
    self.process_pool.join()
    self.recorder.shutdown(reason)
    self.logger.log(self.logger.LL_INFO, "[pluto_intercept_analysis_processor]: shutdown complete")
    self.logger.flush()
