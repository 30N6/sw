import pluto_esm_logger
import pluto_esm_analysis_processor
from pluto_esm_hw_pkg import *
import time
from multiprocessing import Process, Queue

class pluto_esm_analysis_thread:

  def __init__(self, arg):
    self.logger       = pluto_esm_logger.pluto_esm_logger(arg["log_dir"], "pluto_esm_analysis_thread", arg["log_level"])
    self.processor    = pluto_esm_analysis_processor.pluto_esm_analysis_processor(self.logger, arg["log_dir"], arg["config"])
    self.input_queue  = arg["input_queue"]
    self.output_queue = arg["output_queue"]

    self.logger.log(self.logger.LL_INFO, "init: queues={}/{}".format(self.input_queue, self.output_queue))

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
        #TODO: output from processor

    self.shutdown("graceful exit")

  def shutdown(self, reason):
    self.logger.shutdown(reason)
    self.processor.shutdown(reason)


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

    self.output_data_to_render = []

    self.analysis_process = Process(target=pluto_esm_analysis_thread_func,
                               args=({"input_queue": self.input_queue, "output_queue": self.output_queue,
                                      "log_dir": logger.path, "log_level": logger.min_level, "config": sw_config.config}, ))
    self.analysis_process.start()

  def _update_output_queue(self):
    while not self.output_queue.empty():
      data = self.output_queue.get(block=False)
      self.output_data_to_render.append(data)
      self.logger.log(self.logger.LL_DEBUG, "[analysis] _update_output_queue: received data: len={}".format(len(data)))

  def submit_report(self, report):
    self.input_queue.put(report, block=False)

  def update(self):
    self._update_output_queue()

  def shutdown(self):
    self.logger.log(self.logger.LL_INFO, "[analysis] shutdown")
    assert (self.analysis_process.is_alive())
    self.input_queue.put("CMD_STOP", block=False)
    self.analysis_process.join(1.0)
    self.logger.log(self.logger.LL_INFO, "[analysis] analysis_process.exitcode={} is_alive={}".format(self.analysis_process.exitcode, self.analysis_process.is_alive()))
    assert (self.analysis_process.exitcode == 0) #assert (not self.analysis_process.is_alive())
