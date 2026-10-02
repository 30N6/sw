import time
from pluto_intercept_hw_pkg import *
import numpy as np
import time

class pluto_intercept_hw_stats:

  def __init__(self, logger):
    self.logger = logger

    self.dwell_reports_1sec   = []
    self.stream_reports_1sec  = []
    self.last_log_time        = 0

    self.stats = {}

    self.stats["dwell_report_total"]                    = 0
    self.stats["dwell_reports_per_sec"]                 = 0
    self.stats["dwell_windows_total"]                   = 0
    self.stats["dwell_windows_per_sec"]                 = 0

    self.stats["stream_report_total"]                   = 0
    self.stats["stream_reports_per_sec"]                = 0
    self.stats["stream_samples_total"]                  = 0
    self.stats["stream_samples_per_sec"]                = 0

  def update(self):
    now = time.time()

    while (len(self.dwell_reports_1sec) > 0) and ((now - self.dwell_reports_1sec[0]["timestamp"]) > 1.0):
      self.dwell_reports_1sec.pop(0)
    self.stats["dwell_reports_per_sec"] = len(self.dwell_reports_1sec)

    while (len(self.stream_reports_1sec) > 0) and ((now - self.stream_reports_1sec[0]["timestamp"]) > 1.0):
      self.stream_reports_1sec.pop(0)
    self.stats["stream_reports_per_sec"] = len(self.stream_reports_1sec)
    
    self.stats["stream_samples_per_sec"] = 0
    for entry in self.stream_reports_1sec:
      self.stats["stream_samples_per_sec"] += len(entry["stream_report"]["samples"])

    if (now - self.last_log_time) >= 10.0:
      self.last_log_time = now
      self.logger.log(self.logger.LL_INFO, "[hw_stats] stats={}".format(self.stats))

  def submit_report(self, report):
    if "stream_report" in report:
      self._process_stream_report(report)
    elif "dwell_report" in report:
      self._process_dwell_report(report)

  def _process_dwell_report(self, report):
    now = time.time()

    dwell_report = report["dwell_report"]

    self.stats["dwell_report_total"]  += 1
    self.stats["dwell_windows_total"] = dwell_report["window_sequence_num"]

    self.dwell_reports_1sec.append({"timestamp": now, "dwell_report": dwell_report})

  def _process_stream_report(self, report):
    now = time.time()
    
    stream_report = report["stream_report"]

    self.stats["stream_report_total"] += 1
    self.stats["stream_samples_total"] += len(stream_report["samples"])
    
    self.stream_reports_1sec.append({"timestamp": now, "stream_report": stream_report})
 