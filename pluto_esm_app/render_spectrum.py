import pygame
import time

class render_spectrum:

  def __init__(self, surface, sw_config, sequencer):
    self.surface            = surface
    self.sw_config          = sw_config
    self.sequencer          = sequencer
    self.max_freq           = sw_config.max_freq
    self.dwell_bw           = sw_config.config["dwell_constraints"]["freq_step"]
    self.dwell_cal_interval = sw_config.config["fast_lock_config"]["recalibration_interval"]

    self.colors = {}
    self.colors["dwell_old"] = (192, 0, 0)
    self.colors["dwell_new"] = (0, 192, 0)

    self.dwell_cal_height = 0.125

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

    for dwell_freq in self.sequencer.scan_dwells:
      dwell = self.sequencer.scan_dwells[dwell_freq]
      x = dwell_freq / mhz_per_px + rect[0]
      dwell_rect = [x - px_per_dwell/2, rect[1], px_per_dwell, rect[3] * self.dwell_cal_height]
      #print("x={} rect={}".format(x, dwell_rect))
      #break

      if not dwell.fast_lock_profile_valid:
        dwell_color = self.colors["dwell_old"]
      else:
        dwell_color = self._color_interp(self.colors["dwell_new"], self.colors["dwell_old"], (now - dwell.fast_lock_profile_time) / self.dwell_cal_interval)

      pygame.draw.rect(self.surface, dwell_color, dwell_rect, 0)

  def render(self):
    rect_dwell_display = [16, 16,  600, 64]

    self._render_dwell_display(rect_dwell_display)

    pygame.draw.rect(self.surface, (0, 0, 255), [0, 0, 640, 768], 1)
    pygame.draw.rect(self.surface, (0, 128, 128), rect_dwell_display, 1)
    pygame.draw.rect(self.surface, (0, 128, 128), [16, 128, 600, 360], 1)
    pygame.draw.rect(self.surface, (0, 128, 128), [16, 512, 600, 232], 1)

  def process_dwell_updates(self):
    pass