import os
import time
import json

#TODO: shared with pluto_esm

class pluto_ecm_data_recorder:
  def __init__(self, path, prefix, enable):
    self.enable = enable
    if enable:
      self.path = path
      start_time = time.localtime()
      filename = "{}-{:04}{:02}{:02}-{:02}{:02}{:02}.log".format(prefix,
        start_time.tm_year, start_time.tm_mon, start_time.tm_mday,
        start_time.tm_hour, start_time.tm_min, start_time.tm_sec)
      filename = os.path.join(path, filename)
      self.fd = open(filename, "w")

      self.log({"comment": "Logging started"})

  def log(self, data):
    if not self.enable:
      return
    t = time.time()
    t_sec_frac = t % 1.0
    t_loc = time.localtime(t)

    raw_data = {"time": t_loc, "sec_frac": t_sec_frac, "data": data}
    json_data = json.dumps(raw_data, default=vars)
    self.fd.write(json_data + "\n")

  def flush(self):
    if not self.enable:
      return
    self.fd.flush()

  def shutdown(self, reason):
    if not self.enable:
      return
    self.log({"comment": "shutdown - {}".format(reason)})
    self.fd.close()