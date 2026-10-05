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
    self.stats["dwell_windows_total"]                   = 0 #TODO
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
      self.stats["stream_samples_per_sec"] += len(entry["report"]["stream_samples"])

    if (now - self.last_log_time) >= 10.0:
      self.last_log_time = now
      self.logger.log(self.logger.LL_INFO, "[hw_stats] stats={}".format(self.stats))

  def submit_report(self, report):
    if report["msg_type"] == INTERCEPT_REPORT_MESSAGE_TYPE_STREAM:
      self._process_stream_report(report)
    elif report["msg_type"] == INTERCEPT_REPORT_MESSAGE_TYPE_DWELL_STATS:
      self._process_dwell_report(report)

  def _process_dwell_report(self, report):
    now = time.time()

    self.stats["dwell_report_total"]  += 1
    self.stats["dwell_windows_total"] = report["window_seq_num"]

    self.dwell_reports_1sec.append({"timestamp": now, "report": report})

  def _process_stream_report(self, report):
    now = time.time()

    self.stats["stream_report_total"] += 1
    self.stats["stream_samples_total"] += len(report["stream_samples"])

    self.stream_reports_1sec.append({"timestamp": now, "report": report})
