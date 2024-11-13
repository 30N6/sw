import pygame
import time
from pluto_esm_hw_pkg import *
import pluto_esm_dwell_stats_buffer
import pluto_esm_spectrogram
import numpy as np
import math

import cProfile, pstats, io
from pstats import SortKey

class render_spectrum:

  def __init__(self, surface, sw_config, sequencer):
    self.rect_dwell_display               = [16, 4,  600, 16]
    self.rect_waterfall_display_primary   = [16, 48,  600, 320]
    self.rect_waterfall_display_secondary = [16, 416, 600, 320]

    self.surface              = surface
    self.sw_config            = sw_config
    self.sequencer            = sequencer
    self.dwell_buffer         = pluto_esm_dwell_stats_buffer.pluto_esm_dwell_stats_buffer(self.sw_config)
    self.spectrogram          = pluto_esm_spectrogram.pluto_esm_spectrogram(self.sw_config, self.rect_waterfall_display_primary[2:4])
    self.max_freq             = sw_config.max_freq
    self.dwell_bw             = sw_config.config["dwell_config"]["freq_step"]
    self.dwell_cal_interval   = sw_config.config["fast_lock_config"]["recalibration_interval"]
    self.dwell_scan_fade_time = 0.5

    self.colors = {}
    self.colors["cal_old"] = (192, 0, 0)
    self.colors["cal_new"] = (0, 192, 0)
    self.colors["dwell_old"] = (64, 0, 0)
    self.colors["dwell_new"] = (0, 255, 0)
    self.colors["frame_elements"] = (0, 128, 128)
    self.colors["grid_lines"] = (0, 128, 128)
    self.colors["zoom_marker"] = (0, 192, 192)

    self.dwell_cal_height = 0.5
    self.dwell_scan_height = 1 - self.dwell_cal_height

    self.freq_zoom_range = [0, self.max_freq]
    self.freq_zoom_active = True

    self.font = pygame.font.SysFont('Consolas', 12)

    self.pr = cProfile.Profile()

  @staticmethod
  def _color_interp(ca, cb, pct):
    pct = min(1.0, max(0.0, pct))
    return (ca[0] + pct*(cb[0]-ca[0]),
            ca[1] + pct*(cb[1]-ca[1]),
            ca[2] + pct*(cb[2]-ca[2]))

  def _render_dwell_display(self):
    now           = time.time()
    mhz_per_px    = self.max_freq / self.rect_dwell_display[2]
    px_per_dwell  = math.ceil(self.dwell_bw / mhz_per_px)

    # calibration status
    for dwell_freq in self.sequencer.scan_dwells:
      dwell = self.sequencer.scan_dwells[dwell_freq]
      x = dwell_freq / mhz_per_px + self.rect_dwell_display[0]
      dwell_rect = [x - px_per_dwell/2, self.rect_dwell_display[1], px_per_dwell, self.rect_dwell_display[3] * self.dwell_cal_height]
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
      x = dwell_freq / mhz_per_px + self.rect_dwell_display[0]
      dwell_rect = [x - px_per_dwell/2, self.rect_dwell_display[1] + self.rect_dwell_display[3] * (1 - self.dwell_scan_height), px_per_dwell, self.rect_dwell_display[3] * self.dwell_scan_height]
      dwell_color = self._color_interp(self.colors["dwell_new"], self.colors["dwell_old"], (now - dwell_completion_time) / self.dwell_scan_fade_time)
      pygame.draw.rect(self.surface, dwell_color, dwell_rect, 0)

    pygame.draw.rect(self.surface, self.colors["frame_elements"], self.rect_dwell_display, 1)

  def _render_waterfall_display(self):
    #t0 = time.time()

    data = self.spectrogram.get_spectrogram(False, True, self.rect_waterfall_display_primary[2], self.rect_waterfall_display_primary[3])
    surf = pygame.surfarray.make_surface(data)
    self.surface.blit(surf, self.rect_waterfall_display_primary)

    data = self.spectrogram.get_spectrogram(True, True, self.rect_waterfall_display_secondary[2], self.rect_waterfall_display_secondary[3])
    surf = pygame.surfarray.make_surface(data)
    self.surface.blit(surf, self.rect_waterfall_display_secondary)

    pygame.draw.rect(self.surface, self.colors["frame_elements"], self.rect_waterfall_display_primary, 1)
    pygame.draw.rect(self.surface, self.colors["frame_elements"], self.rect_waterfall_display_secondary, 1)

    waterfall_rects = [self.rect_waterfall_display_primary, self.rect_waterfall_display_secondary]

    freq_tick_height = 6
    freq_tick_count = 5

    for i in range(freq_tick_count):
      tick_frac = (i / (freq_tick_count - 1))
      freq_str = "{}".format(round(tick_frac * self.max_freq))
      text_data = self.font.render(freq_str, True, self.colors["frame_elements"])

      for j in range(len(waterfall_rects)):
        x = waterfall_rects[j][0] + tick_frac * (waterfall_rects[j][2] - 1)

        pos_start = (x, waterfall_rects[j][1])
        pos_end   = (x, waterfall_rects[j][1] - freq_tick_height)
        pygame.draw.line(self.surface, self.colors["frame_elements"], pos_start, pos_end)

        text_rect = text_data.get_rect()
        text_rect.centerx = x
        text_rect.bottom = waterfall_rects[j][1] - freq_tick_height - 1
        self.surface.blit(text_data, text_rect)

    if self.freq_zoom_active:
      zoom_marker_width = 8
      mhz_per_px = (self.max_freq / self.rect_waterfall_display_primary[2])

      for i in range(2):
        for j in range(len(waterfall_rects)):
          x = waterfall_rects[j][0] + self.freq_zoom_range[i] / mhz_per_px
          points = [(x - zoom_marker_width/2, waterfall_rects[j][1] + waterfall_rects[j][3] + zoom_marker_width),
                    (x,                       waterfall_rects[j][1] + waterfall_rects[j][3]),
                    (x + zoom_marker_width/2, waterfall_rects[j][1] + waterfall_rects[j][3] + zoom_marker_width)]
          pygame.draw.polygon(self.surface, self.colors["zoom_marker"], points)

    for i in range(len(waterfall_rects)):
      status_str = "testing 12345  testing 12345  testing 12345  testing 12345  testing 12345  testing 12345"
      text_data = self.font.render(status_str, True, self.colors["frame_elements"])
      text_rect = text_data.get_rect()
      text_rect.left = waterfall_rects[i][0]
      text_rect.bottom = waterfall_rects[i][1] + waterfall_rects[i][3] + 24
      self.surface.blit(text_data, text_rect)

  def render(self):

    self._render_dwell_display()
    self._render_waterfall_display()

    pygame.draw.rect(self.surface, (0, 0, 255), [0, 0, 640, 768], 1)


  def update(self):
    #self.pr.enable()

    while len(self.sequencer.dwells_to_render) > 0:
      row_done = self.dwell_buffer.process_dwell_update(self.sequencer.dwells_to_render.pop(0))
      if row_done:
        #self.pr.enable()
        self.spectrogram.process_new_row(self.dwell_buffer)
        #self.pr.disable()
        #s = io.StringIO()
        #sortby = SortKey.CUMULATIVE
        #ps = pstats.Stats(self.pr, stream=s).sort_stats(sortby)
        #ps.print_stats()
        #print(s.getvalue())
