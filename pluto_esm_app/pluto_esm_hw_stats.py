import time
from pluto_esm_hw_pkg import *
import numpy as np
import time

class pluto_esm_hw_stats:

  def __init__(self, logger):
    self.logger = logger

    self.pdw_summaries_1sec = []
    self.dwell_reports_1sec = []
    self.first_sequence_dwell_timestamp = 0

    self.matched_reports    = []
    self.pdw_summaries_scan = []
    self.dwell_reports_scan = []

    self.ts_prev_dwell_end  = 0
    self.ts_prev_pdw_end    = 0

    self.last_log_time      = 0

    self.stats = {}
    self.stats["dwells_per_sec"]                  = 0
    self.stats["scan_time"]                       = 0
    self.stats["pps_total"]                       = 0
    self.stats["pps_dropped"]                     = 0
    self.stats["scan_pulses_total"]               = 0
    self.stats["scan_pulses_dropped"]             = 0
    self.stats["pulses_total"]                    = 0
    self.stats["pulses_dropped"]                  = 0
    self.stats["pulses_accepted"]                 = 0
    self.stats["scan_ack_delay_report"]           = 0
    self.stats["scan_ack_delay_sample_proc"]      = 0
    self.stats["dwell_coverage_fine"]             = 0
    self.stats["pdw_coverage_fine"]               = 0
    self.stats["dwell_coverage_coarse"]           = 0
    self.stats["pdw_coverage_coarse"]             = 0
    self.stats["dwell_requested_duration_total"]  = 0
    self.stats["dwell_actual_duration_total"]     = 0
    self.stats["pdw_requested_duration_total"]    = 0
    self.stats["pdw_actual_duration_total"]       = 0
    self.stats["dwell_time_total"]                = 0
    self.stats["dwell_time_active"]               = 0
    self.stats["pdw_time_total"]                  = 0
    self.stats["pdw_time_active"]                 = 0
    self.stats["pdw_dwells_missing"]              = 0

  def update(self):
    now = time.time()

    self.stats["dwell_coverage_fine"]   = self.stats["dwell_actual_duration_total"] / max(1, self.stats["dwell_requested_duration_total"])
    self.stats["pdw_coverage_fine"]     = self.stats["pdw_actual_duration_total"]   / max(1, self.stats["pdw_requested_duration_total"])
    self.stats["dwell_coverage_coarse"] = self.stats["dwell_time_active"]           / max(1, self.stats["dwell_time_total"])
    self.stats["pdw_coverage_coarse"]   = self.stats["pdw_time_active"]             / max(1, self.stats["pdw_time_total"])

    while (len(self.dwell_reports_1sec) > 0) and ((now - self.dwell_reports_1sec[0]["timestamp"]) > 1.0):
      self.dwell_reports_1sec.pop(0)
    self.stats["dwells_per_sec"] = len(self.dwell_reports_1sec)

    while (len(self.pdw_summaries_1sec) > 0) and ((now - self.pdw_summaries_1sec[0]["timestamp"]) > 1.0):
      self.pdw_summaries_1sec.pop(0)

    pps_total = 0
    pps_dropped = 0
    for summary in self.pdw_summaries_1sec:
      pps_total   += summary["pdw_summary_report"]["dwell_pulse_total_count"]
      pps_dropped += summary["pdw_summary_report"]["dwell_pulse_drop_count"]
    self.stats["pps_total"] = pps_total
    self.stats["pps_dropped"] = pps_dropped

    if (len(self.matched_reports) > 0) and self.matched_reports[-1]["dwell_report"]["last_in_sequence"]:
      #assert (self.matched_reports[0]["dwell_report"]["first_in_sequence"]) #drops are possible when PDW dwells are missed
      scan_pulses_total           = 0
      scan_pulses_dropped         = 0
      scan_ack_delay_report       = 0
      scan_ack_delay_sample_proc  = 0
      for entry in self.matched_reports:
        pdw_report    = entry["pdw_summary_report"]
        dwell_report  = entry["dwell_report"]

        scan_pulses_total           += pdw_report["dwell_pulse_total_count"]
        scan_pulses_dropped         += pdw_report["dwell_pulse_drop_count"]
        scan_ack_delay_report       += pdw_report["ack_delay_report"]
        scan_ack_delay_sample_proc  += pdw_report["ack_delay_sample_processor"]

      self.stats["scan_pulses_total"]           = scan_pulses_total
      self.stats["scan_pulses_dropped"]         = scan_pulses_dropped
      self.stats["scan_ack_delay_report"]       = scan_ack_delay_report * FAST_CLOCK_PERIOD
      self.stats["scan_ack_delay_sample_proc"]  = scan_ack_delay_sample_proc * FAST_CLOCK_PERIOD
      self.matched_reports = []

      if (now - self.last_log_time) >= 10.0:
        self.logger.log(self.logger.LL_INFO, "[hw_stats] stats={}".format(self.stats))

  def submit_report(self, report):
    if "pdw_summary_report" in report:
      self._process_pdw_summary_report(report)
    elif "pdw_pulse_report" in report:
      self._process_pdw_pulse_report(report)
    elif "dwell_report" in report:
      self._process_dwell_report(report)

  def _update_matched_report_stats(self, matched_report):
    pdw_report = matched_report["pdw_summary_report"]
    dwell_report = matched_report["dwell_report"]["dwell_report"]

    self.stats["dwell_requested_duration_total"] += dwell_report["duration_requested"]
    self.stats["dwell_actual_duration_total"]    += dwell_report["dwell_duration"]
    self.stats["pdw_requested_duration_total"]   += dwell_report["duration_requested"]
    self.stats["pdw_actual_duration_total"]      += pdw_report["dwell_duration"]

    self.stats["dwell_time_total"]    += (dwell_report["ts_dwell_end"] - self.ts_prev_dwell_end)
    self.stats["dwell_time_active"]   += dwell_report["dwell_duration"]
    self.stats["pdw_time_total"]      += (pdw_report["dwell_start_time"] + pdw_report["dwell_duration"] - self.ts_prev_pdw_end)
    self.stats["pdw_time_active"]     += pdw_report["dwell_duration"]

    self.ts_prev_dwell_end  = dwell_report["ts_dwell_end"]
    self.ts_prev_pdw_end    = pdw_report["dwell_start_time"] + pdw_report["dwell_duration"]

  def _match_dwell_reports(self):
    if (len(self.dwell_reports_scan) == 0) or (len(self.pdw_summaries_scan) == 0):
      return

    pdw_seq_num = self.pdw_summaries_scan[0]["pdw_summary_report"]["dwell_seq_num"]
    dwell_seq_num = self.dwell_reports_scan[0]["dwell_report"]["dwell_seq_num"]

    if pdw_seq_num != dwell_seq_num:
      assert (pdw_seq_num > dwell_seq_num)
      self.logger.log(self.logger.LL_WARN, "[hw_stats] _match_dwell_reports: missed PDW dwell detected! dwell_seq_num={} pdw_seq_num={}".format(dwell_seq_num, pdw_seq_num))
      self.dwell_reports_scan.pop(0)
      self.stats["pdw_dwells_missing"] += 1
      return

    self.matched_reports.append({"pdw_summary_report": self.pdw_summaries_scan.pop(0)["pdw_summary_report"], "dwell_report": self.dwell_reports_scan.pop(0)})
    self._update_matched_report_stats(self.matched_reports[-1])

  def _process_dwell_report(self, report):
    now = time.time()

    if report["first_in_sequence"]:
      self.first_sequence_dwell_timestamp = now

    if report["last_in_sequence"]:
      self.stats["scan_time"] = now - self.first_sequence_dwell_timestamp

    if self.ts_prev_dwell_end == 0:
      self.ts_prev_dwell_end = report["dwell_report"]["ts_dwell_end"]

    self.dwell_reports_1sec.append({"timestamp": now, "dwell_report": report["dwell_report"]})
    self.dwell_reports_scan.append(report)
    self._match_dwell_reports()

  def _process_pdw_summary_report(self, report):
    now = time.time()

    self.stats["pulses_total"] += report["pdw_summary_report"]["dwell_pulse_total_count"]
    self.stats["pulses_dropped"] += report["pdw_summary_report"]["dwell_pulse_drop_count"]
    self.stats["pulses_accepted"] = self.stats["pulses_total"] - self.stats["pulses_dropped"]

    if self.ts_prev_pdw_end == 0:
      self.ts_prev_pdw_end = report["pdw_summary_report"]["dwell_start_time"] + report["pdw_summary_report"]["dwell_duration"]

    self.pdw_summaries_1sec.append({"timestamp": now, "pdw_summary_report": report["pdw_summary_report"]})
    self.pdw_summaries_scan.append(report)
    self._match_dwell_reports()

  def _process_pdw_pulse_report(self, report):
    pass
