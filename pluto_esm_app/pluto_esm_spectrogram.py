import pygame
import time
from pluto_esm_hw_pkg import *
import numpy as np
import math

class pluto_esm_spectrogram:

  def __init__(self, surface, sw_config, sequencer):
    self.surface              = surface
    self.sw_config            = sw_config
    self.sequencer            = sequencer
    self.max_freq             = sw_config.max_freq
    self.dwell_bw             = sw_config.config["dwell_constraints"]["freq_step"]
    self.dwell_cal_interval   = sw_config.config["fast_lock_config"]["recalibration_interval"]
    self.dwell_scan_fade_time = 0.2

    self.colors = {}
    self.colors["cal_old"] = (192, 0, 0)
    self.colors["cal_new"] = (0, 192, 0)
    self.colors["dwell_old"] = (64, 0, 0)
    self.colors["dwell_new"] = (0, 255, 0)

    self.dwell_cal_height = 0.125
    self.dwell_scan_height = 1 - self.dwell_cal_height

    self.num_channels     = ESM_NUM_CHANNELS_NARROW
    self.channel_spacing  = (ADC_CLOCK_FREQUENCY / self.num_channels) / 1e6

    self.max_buffer_age     = 6000.0 / FAST_CLOCK_PERIOD
    self.dwell_data_dtype   = np.dtype([("time", "u8"), ("freq", "f4"), ("avg_power", "f4"), ("peak_power", "f4")])
    self.dwell_data_buffer  = np.zeros(self.num_channels, self.dwell_data_dtype)

    self.font = pygame.font.SysFont('Consolas', 14)

  @staticmethod
  def _color_interp(ca, cb, pct):
    pct = min(1.0, max(0.0, pct))
    return (ca[0] + pct*(cb[0]-ca[0]),
            ca[1] + pct*(cb[1]-ca[1]),
            ca[2] + pct*(cb[2]-ca[2]))

  def _render_dwell_display(self, rect):
    now           = time.time()
    mhz_per_px    = self.max_freq / rect[2]
    px_per_dwell  = self.dwell_bw / mhz_per_px

    # calibration status
    for dwell_freq in self.sequencer.scan_dwells:
      dwell = self.sequencer.scan_dwells[dwell_freq]
      x = dwell_freq / mhz_per_px + rect[0]
      dwell_rect = [x - px_per_dwell/2, rect[1], px_per_dwell, rect[3] * self.dwell_cal_height]
      #print("x={} rect={}".format(x, dwell_rect))
      #break

      if not dwell.fast_lock_profile_valid:
        dwell_color = self.colors["cal_old"]
      else:
        dwell_color = self._color_interp(self.colors["cal_new"], self.colors["cal_old"], (now - dwell.fast_lock_profile_time) / self.dwell_cal_interval)
      pygame.draw.rect(self.surface, dwell_color, dwell_rect, 0)

    # scan dwells
    for dwell_freq in self.sequencer.dwell_history:
      dwell_completion_time = self.sequencer.dwell_history[dwell_freq]
      x = dwell_freq / mhz_per_px + rect[0]
      dwell_rect = [x - px_per_dwell/2, rect[1] + rect[3] * (1 - self.dwell_scan_height), px_per_dwell, rect[3] * self.dwell_scan_height]
      dwell_color = self._color_interp(self.colors["dwell_new"], self.colors["dwell_old"], (now - dwell_completion_time) / self.dwell_scan_fade_time)
      pygame.draw.rect(self.surface, dwell_color, dwell_rect, 0)

  def _render_waterfall_display(self, rect):
    pass

  def _render_state(self):
    state_str = "{:>20} {:>16}".format(self.sequencer.state, self.sequencer.dwell_state)
    text_data = self.font.render(state_str, True, (0, 192, 192))
    text_rect = text_data.get_rect()
    text_rect.left = 16
    text_rect.bottom = 792
    self.surface.blit(text_data, text_rect)

  def render(self):
    rect_dwell_display = [16, 16,  600, 64]
    rect_waterfall_display = [16, 128, 600, 360]

    self._render_dwell_display(rect_dwell_display)
    self._render_waterfall_display(rect_waterfall_display)
    self._render_state()

    pygame.draw.rect(self.surface, (0, 0, 255), [0, 0, 640, 768], 1)
    pygame.draw.rect(self.surface, (0, 128, 128), rect_dwell_display, 1)
    pygame.draw.rect(self.surface, (0, 128, 128), rect_waterfall_display, 1)
    pygame.draw.rect(self.surface, (0, 128, 128), [16, 512, 600, 232], 1)


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

