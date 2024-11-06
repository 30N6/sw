import os
import time

class pluto_esm_logger:
  LL_DEBUG  = 0
  LL_INFO   = 1
  LL_WARN   = 2
  LL_ERROR  = 3

  def __init__(self, path, prefix, min_level):
    self.path = path
    self.min_level = min_level
    start_time = time.localtime()
    filename = "{}-{:04}{:02}{:02}-{:02}{:02}{:02}.log".format(prefix,
      start_time.tm_year, start_time.tm_mon, start_time.tm_mday,
      start_time.tm_hour, start_time.tm_min, start_time.tm_sec)
    filename = os.path.join(path, filename)
    self.fd = open(filename, "w")
    self.log(self.LL_INFO, "Logging started")

  def log(self, level, string):
    if level < self.min_level:
      return
    t = time.time()
    t_sec = t % 60
    t_loc = time.localtime(t)

    self.fd.write("[{:04}-{:02}-{:02} {:02}:{:02}:{:09.6f}] {}\n".format(t_loc.tm_year, t_loc.tm_mon, t_loc.tm_mday, t_loc.tm_hour, t_loc.tm_min, t_sec, string))

  def flush(self):
    self.fd.flush()

  def shutdown(self, reason):
    self.log(self.LL_INFO, "shutdown - {}".format(reason))
    self.fd.close()