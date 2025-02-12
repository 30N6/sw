import pluto_ecm_logger
import pluto_ecm_analysis_processor
from pluto_ecm_hw_pkg import *
import time
import multiprocessing
from multiprocessing import Process, Queue
import traceback
import copy

import cProfile, pstats, io
from pstats import SortKey

class pluto_ecm_analysis_thread:

  def __init__(self, arg):
    self.input_queue  = arg["input_queue"]
    self.output_queue = arg["output_queue"]
    self.logger       = pluto_ecm_logger.pluto_ecm_logger(arg["log_dir"], "pluto_ecm_analysis_thread", arg["log_level"])
    self.processor    = pluto_ecm_analysis_processor.pluto_ecm_analysis_processor(self.logger, arg["log_dir"], arg["config"], self.output_queue)

    self.logger.log(self.logger.LL_INFO, "init: queues={}/{}, current_process={}".format(self.input_queue, self.output_queue, multiprocessing.current_process()))

  def _send_tracked_signals(self):
    while len(self.processor.data_to_render) > 0:
      self.output_queue.put(self.processor.data_to_render.pop(0))

  def run(self):
    running = True

    #self.pr = cProfile.Profile()

    while running:
      #read off data from the queue before calling update() - helps ensure a clean shutdown
      while not self.input_queue.empty():
        data = self.input_queue.get()
        if isinstance(data, dict):
          #self.logger.log(self.logger.LL_DEBUG, data)
          self.processor.submit_data(data)
        else:
          if data == "CMD_STOP":
            self.logger.log(self.logger.LL_INFO, "CMD_STOP")
            running = False
          else:
            raise RuntimeError("invalid command")
            running = False

      #self.pr.enable()
      self.processor.update()
      self._send_tracked_signals()

      #self.pr.disable()
      #s = io.StringIO()
      #sortby = SortKey.CUMULATIVE
      #ps = pstats.Stats(self.pr, stream=s).sort_stats(sortby)
      #ps.print_stats()
      #print(s.getvalue())

    self.shutdown("graceful exit")

  def shutdown(self, reason):
    self.processor.shutdown(reason)
    self.logger.shutdown(reason)


def pluto_ecm_analysis_thread_func(arg):
  thread = pluto_ecm_analysis_thread(arg)
  try:
    thread.run()
  except KeyboardInterrupt:
    thread.shutdown("interrupted")


class pluto_ecm_analysis_runner:
  def __init__(self, logger, sw_config):
    self.logger       = logger
    self.input_queue  = Queue()
    self.output_queue = Queue()
    self.running      = True

    self.scan_results             = {}
    self.scan_seq_num             = -1
    self.data_to_render           = []
    self.signal_processing_delay  = 0


    self.analysis_process = Process(target=pluto_ecm_analysis_thread_func,
                               args=({"input_queue": self.input_queue, "output_queue": self.output_queue,
                                      "log_dir": logger.path, "log_level": logger.min_level, "config": sw_config.config}, ))
    self.analysis_process.start()

  def _update_output_queue(self):
    while not self.output_queue.empty():
      data = self.output_queue.get(block=False)

      if "scan_results" in data:
        self.scan_results[data["scan_results"]["freq"]] = data["scan_results"]
      elif "scan_seq_num" in data:
        self.scan_seq_num = data["scan_seq_num"]
      elif "confirmed_signals" in data:
        self.data_to_render.append(data)
        if len(data["confirmed_signals"]) > 0:
          self.signal_processing_delay = data["confirmed_signals"][0]["processing_delay"]
      elif "scan_signals" in data:
        self.data_to_render.append(data)
      elif "signal_processing_delay" in data:
        self.signal_processing_delay = data["signal_processing_delay"]
      else:
        raise RuntimeError("unexpected data in output queue")

      self.logger.log(self.logger.LL_DEBUG, "[analysis] _update_output_queue: received data: len={} data={}".format(len(data), data))

  def submit_data(self, report):
    if self.running:
      self.input_queue.put(report, block=False)
    else:
      self.logger.log(self.logger.LL_INFO, "[analysis] submit_data: shutting down -- report dropped: {}".format(report))

  def update(self):
    self._update_output_queue()

  def shutdown(self):
    self.running = False
    self.logger.log(self.logger.LL_INFO, "[analysis] shutdown")
    if self.analysis_process.is_alive():
      self.input_queue.put("CMD_STOP", block=False)
      self.analysis_process.join(1.0)
      self.logger.log(self.logger.LL_INFO, "[analysis] shutdown: analysis_process.exitcode={} is_alive={}".format(self.analysis_process.exitcode, self.analysis_process.is_alive()))
    else:
      self.logger.log(self.logger.LL_INFO, "[analysis] shutdown: analysis_process already dead, exitcode={}".format(self.analysis_process.exitcode))
    self.logger.flush()

    while not self.input_queue.empty():
      data = self.input_queue.get(block=False)
      self.logger.log(self.logger.LL_INFO, "[analysis] shutdown: input_queue data dropped")
    while not self.output_queue.empty():
      data = self.output_queue.get(block=False)
      self.logger.log(self.logger.LL_INFO, "[analysis] shutdown: output_queue data dropped")
