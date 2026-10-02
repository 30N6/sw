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

    self.data_to_render = []

  def submit_data(self, data):
    pass

  def update(self):
    pass

  def shutdown(self, reason):
    self.logger.log(self.logger.LL_INFO, "[pluto_intercept_analysis_processor]: shutdown started - reason={}".format(reason))
    self.recorder.shutdown(reason)
    self.logger.log(self.logger.LL_INFO, "[pluto_intercept_analysis_processor]: shutdown complete")
    self.logger.flush()
