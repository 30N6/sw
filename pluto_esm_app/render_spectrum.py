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
    self.rect_waterfall_display = [16, 128, 600, 360]

    self.surface              = surface
    self.sw_config            = sw_config
    self.sequencer            = sequencer
    self.dwell_buffer         = pluto_esm_dwell_stats_buffer.pluto_esm_dwell_stats_buffer(self.sw_config)
    self.spectrogram          = pluto_esm_spectrogram.pluto_esm_spectrogram(self.sw_config, self.rect_waterfall_display[2:4])
    self.max_freq             = sw_config.max_freq
    self.dwell_bw             = sw_config.config["dwell_config"]["freq_step"]
    self.dwell_cal_interval   = sw_config.config["fast_lock_config"]["recalibration_interval"]
    self.dwell_scan_fade_time = 0.5

    self.colors = {}
    self.colors["cal_old"] = (192, 0, 0)
    self.colors["cal_new"] = (0, 192, 0)
    self.colors["dwell_old"] = (64, 0, 0)
    self.colors["dwell_new"] = (0, 255, 0)

    self.dwell_cal_height = 0.125
    self.dwell_scan_height = 1 - self.dwell_cal_height

    self.font = pygame.font.SysFont('Consolas', 14)

    self.last_saved_index = 0

    self.pr = cProfile.Profile()

  @staticmethod
  def _color_interp(ca, cb, pct):
    pct = min(1.0, max(0.0, pct))
    return (ca[0] + pct*(cb[0]-ca[0]),
            ca[1] + pct*(cb[1]-ca[1]),
            ca[2] + pct*(cb[2]-ca[2]))

  def _render_dwell_display(self, rect):
    now           = time.time()
    mhz_per_px    = self.max_freq / rect[2]
    px_per_dwell  = math.ceil(self.dwell_bw / mhz_per_px)

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
    #t0 = time.time()

    data = self.spectrogram.get_spectrogram(False, rect[2], rect[3])
    surf = pygame.surfarray.make_surface(data)
    #t1 = time.time()

    #print("render_waterfall: t1-t0={}".format(t1-t0))

    #if self.spectrogram.dwell_data_row_index % 32 == 31:
    #  if self.last_saved_index != self.spectrogram.dwell_data_row_index:
    #    np.savetxt("./dwell_data_channel_peak.txt", self.spectrogram.dwell_data_channel_peak, "%u")
    #    np.savetxt("./dwell_data_channel_accum.txt", self.spectrogram.dwell_data_channel_accum, "%u")
    #    np.savetxt("./dwell_data_channel_duration.txt", self.spectrogram.dwell_data_channel_duration, "%u")
    #
    #  self.last_saved_index = self.spectrogram.dwell_data_row_index


    self.surface.blit(surf, rect)

    #outimage = np.array(image, np.ubyte)
    #outimage = Image.fromarray(outimage, mode='L')
    #outimage = outimage.convert('RGBA')
    #strFormat = 'RGBA'
    #raw_str = outimage.tobytes("raw", strFormat)
    #surface = pygame.image.fromstring(raw_str, outimage.size, 'RGBA')

    pass

  def render(self):
    rect_dwell_display = [16, 16,  600, 64]

    self._render_dwell_display(rect_dwell_display)
    self._render_waterfall_display(self.rect_waterfall_display)

    pygame.draw.rect(self.surface, (0, 0, 255), [0, 0, 640, 768], 1)
    pygame.draw.rect(self.surface, (0, 128, 128), rect_dwell_display, 1)
    pygame.draw.rect(self.surface, (0, 128, 128), self.rect_waterfall_display, 1)
    pygame.draw.rect(self.surface, (0, 128, 128), [16, 512, 600, 232], 1)

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
