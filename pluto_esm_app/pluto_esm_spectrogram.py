import pygame
import time
from pluto_esm_hw_pkg import *
import numpy as np
import math

class pluto_esm_spectrogram:

  def __init__(self, surface, sw_config, sequencer):
    self.max_freq             = sw_config.max_freq
    self.dwell_bw             = sw_config.config["dwell_config"]["freq_step"]
    self.adjusted_max_freq    = self.max_freq + self.dwell_bw / 2

    self.num_channels     = ESM_NUM_CHANNELS_NARROW
    self.channel_spacing  = (ADC_CLOCK_FREQUENCY / self.num_channels) / 1e6
    assert (self.channel_spacing == sw_config.config["dwell_config"]["channel_step"]

    num_columns = int(round(self.adjusted_max_freq / self.channel_spacing))
    num_rows    = 1024 #config?

    self.dwell_data_channel_accum = np.zeros((num_rows, num_columns), dtype=np.float64)
    self.dwell_data_channel_peak  = np.zeros((num_rows, num_columns), dtype=np.float32)
    self.dwell_data_channel_time  = np.zeros((num_rows, num_columns), dtype=np.uint32)


  def process_dwell_updates(self):
    while len(self.sequencer.dwells_to_render) > 0:
      entry         = self.sequencer.dwells_to_render.pop(0)
      dwell_data    = entry["dwell_data"]
      dwell_report  = entry["dwell_report"]

      assert (dwell_report["num_channels"] == self.num_channels)
      assert (len(dwell_report["channel_data"]) == self.num_channels)
      assert (dwell_report["frequency"] == dwell_data.frequency)

      channel_data = np.zeros(self.num_channels - 1, self.dwell_data_dtype) #skip channel (wraps around)
      for i in range(1, self.num_channels):
        entry = dwell_report["channel_data"][i]
        assert (entry["index"] == i)
        channel_data[i - 1]["time"]       = dwell_report["ts_dwell_start"]
        channel_data[i - 1]["freq"]       = dwell_report["frequency"] - self.channel_spacing * (self.num_channels / 2 - i)  #TODO: not sure if this is off by one -- need hw testing
        channel_data[i - 1]["avg_power"]  = entry["accum"]  / dwell_report["num_samples"]
        channel_data[i - 1]["peak_power"] = entry["max"]

      self.dwell_data_buffer = np.concatenate((self.dwell_data_buffer, channel_data), casting="no")
      #print(self.dwell_data_buffer)

      print("dwell_duration = {} {}".format(dwell_report["ts_dwell_end"] - dwell_report["ts_dwell_start"], (dwell_report["ts_dwell_end"] - dwell_report["ts_dwell_start"]) * FAST_CLOCK_PERIOD))

    newest_timestamp = self.dwell_data_buffer[-1]["time"]
    max_age = (newest_timestamp - self.dwell_data_buffer[0]["time"]) * FAST_CLOCK_PERIOD
    print("max_age={} len={}".format(max_age, self.dwell_data_buffer.size))

  def update(self):
    self.process_dwell_updates()

