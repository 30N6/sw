import pluto_esm_logger
import pluto_esm_analysis_processor
from pluto_esm_hw_pkg import *
import time
import multiprocessing
from multiprocessing import Process, Queue

class pluto_esm_analysis_thread:

  def __init__(self, arg):
    self.logger       = pluto_esm_logger.pluto_esm_logger(arg["log_dir"], "pluto_esm_analysis_thread", arg["log_level"])
    self.processor    = pluto_esm_analysis_processor.pluto_esm_analysis_processor(self.logger, arg["log_dir"], arg["config"])
    self.input_queue  = arg["input_queue"]
    self.output_queue = arg["output_queue"]

    self.logger.log(self.logger.LL_INFO, "init: queues={}/{}, current_process={}".format(self.input_queue, self.output_queue, multiprocessing.current_process()))

  def _send_tracked_emitters(self):
    if len(self.processor.confirmed_pulsed_signals_to_render) > 0:
      self.output_queue.put({"pulsed_emitters": self.processor.confirmed_pulsed_signals_to_render})
      self.processor.confirmed_pulsed_signals_to_render = []

    if len(self.processor.confirmed_cw_primary_signals_to_render) > 0:
      self.output_queue.put({"cw_emitters_primary": self.processor.confirmed_cw_primary_signals_to_render})
      self.processor.confirmed_cw_primary_signals_to_render = []

    if len(self.processor.confirmed_cw_secondary_signals_to_render) > 0:
      self.output_queue.put({"cw_emitters_secondary": self.processor.confirmed_cw_secondary_signals_to_render})
      self.processor.confirmed_cw_secondary_signals_to_render = []

  def run(self):
    running = True

    while running:
      if not self.input_queue.empty():
        data = self.input_queue.get()
        if isinstance(data, dict):
          self.logger.log(self.logger.LL_DEBUG, data)
          self.processor.submit_report(data)
        else:
          if data == "CMD_STOP":
            self.logger.log(self.logger.LL_INFO, "CMD_STOP")
            running = False
          else:
            raise RuntimeError("invalid command")
            running = False

      self.processor.update()
      self._send_tracked_emitters()

    self.shutdown("graceful exit")

  def shutdown(self, reason):
    self.processor.shutdown(reason)
    self.logger.shutdown(reason)


def pluto_esm_analysis_thread_func(arg):
  thread = pluto_esm_analysis_thread(arg)
  try:
    thread.run()
  except KeyboardInterrupt:
    thread.shutdown("interrupted")


class pluto_esm_analysis_runner:
  def __init__(self, logger, sw_config):
    self.logger       = logger
    self.input_queue  = Queue()
    self.output_queue = Queue()
    self.running      = True

    self.output_data_to_render = []

    self.analysis_process = Process(target=pluto_esm_analysis_thread_func,
                               args=({"input_queue": self.input_queue, "output_queue": self.output_queue,
                                      "log_dir": logger.path, "log_level": logger.min_level, "config": sw_config.config}, ))
    self.analysis_process.start()

  def _update_output_queue(self):
    while not self.output_queue.empty():
      data = self.output_queue.get(block=False)
      self.output_data_to_render.append(data)
      self.logger.log(self.logger.LL_DEBUG, "[analysis] _update_output_queue: received data: len={} data={}".format(len(data), data))

  def submit_report(self, report):
    if self.running:
      self.input_queue.put(report, block=False)
    else:
      self.logger.log(self.logger.LL_INFO, "[analysis] submit_report: shutting down -- report dropped: {}".format(report))

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
