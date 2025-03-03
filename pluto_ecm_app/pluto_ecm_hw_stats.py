import time
from pluto_ecm_hw_pkg import *
import numpy as np
import time

class pluto_ecm_hw_stats:

  def __init__(self, logger):
    self.logger = logger

    self.dwell_reports_1sec = []
    self.first_sequence_dwell_timestamp = 0

    self.ts_prev_dwell_end    = 0
    self.last_log_time        = 0

    self.stats = {}

    self.stats["dwell_report_total"]                    = 0
    self.stats["dwell_requested_meas_duration_total"]   = 0
    self.stats["dwell_time_active_meas"]                = 0
    self.stats["dwell_time_active_total"]               = 0
    self.stats["dwell_time_gap_total"]                  = 0
    self.stats["dwell_time_total"]                      = 0
    self.stats["dwell_cycles_meas"]                     = 0
    self.stats["dwell_cycles_tx"]                       = 0
    self.stats["dwell_cycles_total"]                    = 0
    self.stats["dwell_cycles_tx_sec"]                   = 0

    self.stats["drfm_summary_report_total"]             = 0
    self.stats["drfm_dwells_with_writes"]               = 0
    self.stats["drfm_dwells_with_reads"]                = 0
    self.stats["drfm_total_channel_write_report_delay"] = 0
    self.stats["drfm_total_summary_write_report_delay"] = 0
    self.stats["drfm_total_summary_start_report_delay"] = 0
    self.stats["drfm_channel_report_total"]             = 0

    self.stats["dwell_time_total_sec"]                  = 0
    self.stats["dwells_per_sec"]                        = 0
    self.stats["scan_time"]                             = 0
    self.stats["dwell_coverage_meas_req"]               = 0
    self.stats["dwell_coverage_meas_active"]            = 0
    self.stats["dwell_coverage_total_meas"]             = 0
    self.stats["dwell_coverage_total_all"]              = 0
    self.stats["dwell_cycles_meas_frac"]                = 0
    self.stats["dwell_cycles_tx_frac"]                  = 0


    self.stats["drfm_total_channel_write_report_delay_sec"] = 0
    self.stats["drfm_total_summary_write_report_delay_sec"] = 0
    self.stats["drfm_total_summary_start_report_delay_sec"] = 0

  def update(self):
    now = time.time()

    self.stats["dwell_coverage_meas_req"]     = self.stats["dwell_time_active_meas"]  / max(1, self.stats["dwell_requested_meas_duration_total"])
    self.stats["dwell_coverage_meas_active"]  = self.stats["dwell_time_active_meas"]  / max(1, self.stats["dwell_time_active_total"])
    self.stats["dwell_coverage_total_meas"]   = self.stats["dwell_time_active_meas"]  / max(1, self.stats["dwell_time_total"])
    self.stats["dwell_coverage_total_all"]    = self.stats["dwell_time_active_total"] / max(1, self.stats["dwell_time_total"])
    self.stats["dwell_gap_fraction"]          = self.stats["dwell_time_gap_total"]    / max(1, self.stats["dwell_time_total"])
    self.stats["dwell_cycles_meas_frac"]      = self.stats["dwell_cycles_meas"]       / max(1, self.stats["dwell_cycles_total"])
    self.stats["dwell_cycles_tx_frac"]        = self.stats["dwell_cycles_tx"]         / max(1, self.stats["dwell_cycles_total"])
    self.stats["dwell_cycles_tx_sec"]         = self.stats["dwell_cycles_tx"] * FAST_CLOCK_PERIOD

    self.stats["dwell_time_total_sec"]                       = FAST_CLOCK_PERIOD * self.stats["dwell_time_total"]
    self.stats["drfm_total_channel_write_report_delay_frac"] = FAST_CLOCK_PERIOD * self.stats["drfm_total_channel_write_report_delay"] #/ max(1, self.stats["dwell_time_total"])
    self.stats["drfm_total_summary_write_report_delay_frac"] = FAST_CLOCK_PERIOD * self.stats["drfm_total_summary_write_report_delay"] #/ max(1, self.stats["dwell_time_total"])
    self.stats["drfm_total_summary_start_report_delay_frac"] = FAST_CLOCK_PERIOD * self.stats["drfm_total_summary_start_report_delay"] #/ max(1, self.stats["dwell_time_total"])

    while (len(self.dwell_reports_1sec) > 0) and ((now - self.dwell_reports_1sec[0]["timestamp"]) > 1.0):
      self.dwell_reports_1sec.pop(0)
    self.stats["dwells_per_sec"] = len(self.dwell_reports_1sec)

    if (now - self.last_log_time) >= 10.0:
      self.last_log_time = now
      self.logger.log(self.logger.LL_INFO, "[hw_stats] stats={}".format(self.stats))

  def submit_report(self, report):
    if "drfm_summary_report" in report:
      self._process_drfm_summary_report(report)
    elif "drfm_channel_report" in report:
      self._process_drfm_channel_report(report)
    elif "dwell_report" in report:
      self._process_dwell_report(report)

  def _process_dwell_report(self, report):
    now = time.time()

    if report["first_in_sequence"]:
      self.first_sequence_dwell_timestamp = now

    if report["last_in_sequence"]:
      self.stats["scan_time"] = now - self.first_sequence_dwell_timestamp

    dwell_report = report["dwell_report"]

    ts_dwell_end = dwell_report["ts_dwell_start"] + dwell_report["actual_total_duration"]

    if self.ts_prev_dwell_end == 0:
      self.ts_prev_dwell_end = ts_dwell_end

    self.dwell_reports_1sec.append({"timestamp": now, "dwell_report": dwell_report})

    self.stats["dwell_report_total"]                  += 1
    self.stats["dwell_requested_meas_duration_total"] += dwell_report["dwell_entry_measurement_duration"]
    self.stats["dwell_time_active_meas"]              += dwell_report["actual_measurement_duration"]
    self.stats["dwell_time_active_total"]             += dwell_report["actual_total_duration"]
    self.stats["dwell_time_gap_total"]                += dwell_report["ts_dwell_start"] - self.ts_prev_dwell_end
    self.stats["dwell_time_total"]                    += (ts_dwell_end - self.ts_prev_dwell_end)

    self.ts_prev_dwell_end = ts_dwell_end

    self.stats["dwell_cycles_total"]  += dwell_report["cycles_total"]
    self.stats["dwell_cycles_meas"]   += dwell_report["cycles_active_meas"]
    self.stats["dwell_cycles_tx"]     += dwell_report["cycles_active_tx"]

  def _process_drfm_summary_report(self, report):

    drfm_report = report["drfm_summary_report"]

    self.stats["drfm_summary_report_total"]             += 1
    self.stats["drfm_dwells_with_writes"]               += (drfm_report["channel_was_written"] != 0)
    self.stats["drfm_dwells_with_reads"]                += (drfm_report["channel_was_read"] != 0)
    self.stats["drfm_total_channel_write_report_delay"] += drfm_report["report_delay_channel_write"]
    self.stats["drfm_total_summary_write_report_delay"] += drfm_report["report_delay_summary_write"]
    self.stats["drfm_total_summary_start_report_delay"] += drfm_report["report_delay_summary_start"]

  def _process_drfm_channel_report(self, report):
    self.stats["drfm_channel_report_total"] += 1
