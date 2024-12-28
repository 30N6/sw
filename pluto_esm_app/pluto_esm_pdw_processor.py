from pluto_esm_hw_pkg import *
import time
import numpy as np

class pluto_esm_pdw_processor:
  def __init__(self, logger):
    self.logger = logger

    self.dwell_history_pdw = []
    self.dwell_history_accum = []
    self.max_dwell_age = 60 #TODO: config?

    #TODO: config?
    #self.hist_pd  = histogram_multi_level([0, 16383], [1, 4, 16, 64])
    #self.hist_pri = histogram_multi_level([0, 65535], [1, 8, 64, 256])
    #self.hist_pri_pd = histogram_2d([65536, 1024])
    self.hist_pri         = histogram_1d(65536)
    self.hist_pd          = histogram_1d(1024)
    self.dwell_time_accum = {}

    self.scale_factor_pd  = ((ESM_NUM_CHANNELS_NARROW / CHANNELIZER_OVERSAMPLING) * ADC_CLOCK_PERIOD) / 1.0e-6
    self.scale_factor_toa = FAST_CLOCK_PERIOD / 1.0e-6

  def submit_dwell_data(self, combined_dwell_data):
    now = time.time()

    pdws              = combined_dwell_data["pdw_pulse_reports"]
    dwell_num_samples = combined_dwell_data["dwell_num_samples_pdw"]

    dwell_freqs = np.unique([p["channel_frequency"] for p in pdws])
    for channel_freq in dwell_freqs:
      channel_pdws        = [p for p in pdws if (p["channel_frequency"] == channel_freq)]
      channel_num_samples = dwell_num_samples[channel_freq]

      pulse_duration_raw  = np.asarray([p["pulse_duration"] for p in channel_pdws])
      pulse_duration      = pulse_duration_raw * self.scale_factor_pd
      pulse_toa           = np.asarray([p["pulse_start_time"] for p in channel_pdws]) * self.scale_factor_toa
      pulse_pri           = np.diff(pulse_toa)
      #pulse_power         = np.asarray([p["pulse_power_accum"] for p in channel_pdws]) / pulse_duration_raw

      for i in range(len(channel_pdws) - 1):
        channel_pdws[i]["pulse_pri"]      = pulse_pri[i]
        channel_pdws[i]["processor_time"] = now
      channel_pdws[-1]["pulse_pri"]       = -1
      channel_pdws[-1]["processor_time"]  = now

      self.dwell_history_pdw.append({"time": now,
                                 "pdws": channel_pdws,
                                 "channel_freq": channel_freq,
                                 "pulse_duration": pulse_duration,
                                 "pulse_pri": pulse_pri,
                                 #"pulse_power": pulse_power,
                                 "dwell_num_samples": channel_num_samples})
      self.hist_pd.add_dwell_pdws(channel_freq, pulse_duration)
      self.hist_pri.add_dwell_pdws(channel_freq, pulse_pri)

    for channel_freq in dwell_num_samples:
      if channel_freq not in self.dwell_time_accum:
        self.dwell_time_accum[channel_freq] = 0
      self.dwell_time_accum[channel_freq] += dwell_num_samples[channel_freq] #* FAST_CLOCK_PERIOD
    self.dwell_history_accum.append({"time": now, "dwell_num_samples": dwell_num_samples})

  def _scrub_history(self):
    now = time.time()

    while len(self.dwell_history_pdw) > 0:
      if (now - self.dwell_history_pdw[0]["time"]) > self.max_dwell_age:
        removed_dwell = self.dwell_history_pdw.pop(0)
        self.hist_pd.remove_dwell_pdws(removed_dwell["channel_freq"], removed_dwell["pulse_duration"])
        self.hist_pri.remove_dwell_pdws(removed_dwell["channel_freq"], removed_dwell["pulse_pri"])
      else:
        break

    while len(self.dwell_history_accum) > 0:
      if (now - self.dwell_history_accum[0]["time"]) > self.max_dwell_age:
        removed_dwell = self.dwell_history_accum.pop(0)
        for freq in removed_dwell["dwell_num_samples"]:
          self.dwell_time_accum[freq] -= removed_dwell["dwell_num_samples"][freq]
      else:
        break

  def update(self):
    self._scrub_history()


class histogram_1d:
  def __init__(self, bin_count):
    self.bin_count = bin_count
    self.hist_count = {}
    self.data_count = {}

  def add_dwell_pdws(self, freq, data):
    if len(data) == 0:
      return

    if freq not in self.hist_count:
      self.hist_count[freq] = np.zeros(self.bin_count, dtype=np.uint32)
      self.data_count[freq] = 0

    data_index = data.astype(np.uint32)
    data_index[data_index >= self.bin_count] = self.bin_count - 1
    #for i in range(len(data_index)):
    #  index = data_index[i]
    for index in np.nditer(data_index):
      self.hist_count[freq][index] += 1
    self.data_count[freq] += len(data)

  def remove_dwell_pdws(self, freq, data):
    if len(data) == 0:
      return

    data_index = data.astype(np.uint32)
    data_index[data_index >= self.bin_count] = self.bin_count - 1
    self.hist_count[freq][data_index] -= 1
    self.data_count[freq] -= len(data)

  def get_count_in_range(self, freq, hist_range):
    if freq not in self.hist_count:
      return 0

    i_start = int(min(hist_range[0], self.bin_count - 1))
    i_end   = int(min(hist_range[1], self.bin_count))
    assert (i_end > i_start)

    return np.sum(self.hist_count[freq][i_start:i_end])
