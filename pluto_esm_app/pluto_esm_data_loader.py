import os
import time
import json

class pluto_esm_data_loader:
  def __init__(self, logger, filename, speed=5.0):
    self.logger = logger

    self.fd = open(filename, "r")

    first_line = json.loads(self.fd.readline())
    first_time = self._get_entry_time(first_line)

    self.speed = speed

    now = time.time()
    self.initial_time = now
    self.time_offset = now - first_time

    self.logger.log(self.logger.LL_INFO, "[pluto_esm_data_loader] opened {} -- first_time={} offset={}".format(filename, first_time, self.time_offset))

    self.pending_lines = []
    self.lines_processed = 0
    self.input_done = False

  @staticmethod
  def _get_entry_time(entry):
    t_int = time.mktime(tuple(entry["time"]))
    t_frac = entry["sec_frac"]
    return t_int + t_frac

  def _decode_line(self, line):
    entry = json.loads(line)
    t = self._get_entry_time(entry)
    entry["original_time"] = t
    entry["virtual_time"] = t + self.time_offset
    entry.pop("sec_frac")
    return entry

  def get_entries_up_to_time(self, t):
    if self.input_done:
      return []

    adjusted_time = (t - self.initial_time) * self.speed + self.initial_time

    while not self.input_done:
      line = self.fd.readline()
      if len(line) == 0:
        self.logger.log(self.logger.LL_INFO, "[pluto_esm_data_loader] finished reading file -- lines_processed={}".format(self.lines_processed))
        self.input_done = True
        break

      self.lines_processed += 1
      decoded_line = self._decode_line(line)
      self.pending_lines.append(decoded_line)
      if decoded_line["virtual_time"] > adjusted_time:
        break

    r = []
    while len(self.pending_lines) > 0:
      if self.pending_lines[0]["virtual_time"] > adjusted_time:
        break
      r.append(self.pending_lines.pop(0))

    return r
