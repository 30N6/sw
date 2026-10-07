import time
from pluto_intercept_hw_pkg import *
import numpy as np
import time
from collections import deque

class pluto_intercept_hw_stats:

  def __init__(self, logger):
    self.logger = logger

    self.dwell_reports_1sec   = deque()
    self.stream_reports_1sec  = deque()
    self.stream_samples_1sec  = 0
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
    cutoff = now - 1.0

    while self.dwell_reports_1sec and (self.dwell_reports_1sec[0] < cutoff):
      self.dwell_reports_1sec.popleft()
    self.stats["dwell_reports_per_sec"] = len(self.dwell_reports_1sec)

    while self.stream_reports_1sec and (self.stream_reports_1sec[0][0] < cutoff):
      self.stream_samples_1sec -= self.stream_reports_1sec.popleft()[1]
    self.stats["stream_reports_per_sec"] = len(self.stream_reports_1sec)
    self.stats["stream_samples_per_sec"] = self.stream_samples_1sec

    if (now - self.last_log_time) >= 10.0:
      self.last_log_time = now
      self.logger.log(self.logger.LL_INFO, "[hw_stats] stats={}".format(self.stats))

  def submit_report(self, report):
    if report["msg_type"] == INTERCEPT_REPORT_MESSAGE_TYPE_STREAM:
      self._process_stream_report(report)
    elif report["msg_type"] == INTERCEPT_REPORT_MESSAGE_TYPE_DWELL_STATS:
      self._process_dwell_report(report)

  def _process_dwell_report(self, report):
    self.stats["dwell_report_total"]  += 1
    self.stats["dwell_windows_total"] = report["window_seq_num"]

    self.dwell_reports_1sec.append(time.time())

  def _process_stream_report(self, report):
    num_samples = report["stream_samples"].size

    self.stats["stream_report_total"] += 1
    self.stats["stream_samples_total"] += num_samples

    self.stream_reports_1sec.append((time.time(), num_samples))
    self.stream_samples_1sec += num_samples
