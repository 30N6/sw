import pygame
import time
from pluto_intercept_hw_pkg import *
import pluto_intercept_spectrogram
import numpy as np
import math

import cProfile, pstats, io
from pstats import SortKey

class render_spectrum:

  def __init__(self, surface, sw_config, sequencer):

    self.graphics_left                    = 64
    self.graphics_width                   = 512

    self.rect_waterfall                   = [self.graphics_left, 28,    self.graphics_width, 320]
    self.rect_spectrum                    = [self.graphics_left, 368,   self.graphics_width, 128]

    self.surface                          = surface
    self.sw_config                        = sw_config
    self.sequencer                        = sequencer
    self.spectrogram                      = pluto_intercept_spectrogram.pluto_intercept_spectrogram(self.graphics_width, self.rect_waterfall[3], self.rect_spectrum[3])

    self._update_frequency_range()

    #TODO: cleanup
    self.colors = {}
    self.colors["cal_old"]        = (192, 0, 0)
    self.colors["cal_new"]        = (0, 192, 0)
    self.colors["dwell_old"]      = (64, 0, 0)
    self.colors["dwell_new"]      = (0, 255, 0)
    #self.colors["frame_elements"] = (0, 128, 128)
    self.colors["frame_elements"] = (0, 255, 192)
    self.colors["grid_lines"]     = (0, 128, 128)
    self.colors["zoom_marker"]    = (0, 192, 192)
    self.colors["trigger_thresh"] = (192, 192, 0)
    self.colors["trigger_forced"] = (0, 64, 192)

    self.font = pygame.font.SysFont('Consolas', 16)

    self.pr = cProfile.Profile()

  @staticmethod
  def _color_interp(ca, cb, pct):
    pct = min(1.0, max(0.0, pct))
    return (ca[0] + pct*(cb[0]-ca[0]),
            ca[1] + pct*(cb[1]-ca[1]),
            ca[2] + pct*(cb[2]-ca[2]))

  @staticmethod
  def _check_inside_rect(p, r):
    if (p[0] < r[0]) or (p[0] > (r[0] + r[2])):
      return False
    if (p[1] < r[1]) or (p[1] > (r[1] + r[3])):
      return False
    return True

  def _get_spectrum_peaks(self, data, N, zoom_range, mhz_per_px, compute_dB):
    zoomed_data = data[zoom_range[0]:zoom_range[1]]

    if len(zoomed_data) < N:
      return [0], [0]

    idx = np.sort(np.argpartition(zoomed_data, -N)[-N:])
    freq = (zoom_range[0] + idx) * mhz_per_px
    val = zoomed_data[idx]

    if compute_dB:
      return freq, 10*np.log10(val)
    else:
      return freq, val

  def _update_frequency_range(self):
    self.frequency_range  = [ self.sequencer.dwell_data["frequency"] - ADC_CLOCK_FREQUENCY * 1e-6 / 2,
                              self.sequencer.dwell_data["frequency"],
                              self.sequencer.dwell_data["frequency"] + ADC_CLOCK_FREQUENCY * 1e-6 / 2]


  def _render_waterfall_display(self):
    data_w = self.spectrogram.get_waterfall(False)
    surf_w = pygame.surfarray.make_surface(data_w)
    self.surface.blit(surf_w, self.rect_waterfall)

    #TODO: pre-compute
    freq_x = [self.rect_waterfall[0], self.rect_waterfall[0] + self.rect_waterfall[2] // 2, self.rect_waterfall[0] + self.rect_waterfall[2]]

    for i in range(len(freq_x)):
      freq_str = "{:.1f}".format(self.frequency_range[i])
      text_data = self.font.render(freq_str, True, self.colors["frame_elements"])
      text_rect = text_data.get_rect()
      text_rect.centerx = freq_x[i]
      text_rect.centery = self.rect_waterfall[1] - 16
      self.surface.blit(text_data, text_rect)

    pygame.draw.rect(self.surface, self.colors["frame_elements"], self.rect_waterfall, 1)

  def _render_spectrum_display(self):
    data_s = self.spectrogram.get_trace()
    surf_s = pygame.surfarray.make_surface(data_s)
    self.surface.blit(surf_s, self.rect_spectrum)

    pygame.draw.rect(self.surface, self.colors["frame_elements"], self.rect_spectrum, 1)

  def _render_cursor(self):
    cursor_pos          = pygame.mouse.get_pos()
    cursor_in_waterfall = self._check_inside_rect(cursor_pos, self.rect_waterfall)
    cursor_in_spectrum  = self._check_inside_rect(cursor_pos, self.rect_spectrum)

    if cursor_in_waterfall or cursor_in_spectrum:
      if cursor_in_waterfall:
        x_frac = (cursor_pos[0] - self.rect_waterfall[0]) / self.rect_waterfall[2]
        y_text = self.rect_waterfall[1] + self.rect_waterfall[3]/2
      else:
        x_frac = (cursor_pos[0] - self.rect_spectrum[0]) / self.rect_spectrum[2]
        y_text = self.rect_spectrum[1] + self.rect_spectrum[3]/2

      x_text = self.graphics_left + self.graphics_width + 8;
      freq = self.frequency_range[0] + x_frac * (self.frequency_range[2] - self.frequency_range[0])

      s = "{:<.1f}".format(freq)
      text_data = self.font.render(s, True, self.colors["frame_elements"])
      text_rect = text_data.get_rect()
      text_rect.left = x_text
      text_rect.bottom = y_text
      self.surface.blit(text_data, text_rect)

  def _render_dwell_display(self):
    now           = time.time()

    #mhz_per_px    = self.max_freq / self.rect_dwell_display[2]
    #px_per_dwell  = math.ceil(self.dwell_bw / mhz_per_px)

    # calibration status
    for i in range(len(self.sequencer.fast_lock_manager.fast_lock_cal_state)):
      cal_state = self.sequencer.fast_lock_manager.fast_lock_cal_state[i]
      dwell_rect = [self.freq_coords[i] - self.dwell_pane_width/2, self.rect_dwell_display[1], self.dwell_pane_width, self.rect_dwell_display[3] * 0.33]

      if not cal_state.fast_lock_profile_valid:
        cal_color = self.colors["cal_old"]
      else:
        cal_color = self._color_interp(self.colors["cal_new"], self.colors["cal_old"], (now - cal_state.fast_lock_profile_time) / self.dwell_cal_interval)
      pygame.draw.rect(self.surface, cal_color, dwell_rect, 0)

    # scan dwells
    for i in range(self.dwell_count):
      freq = self.dwell_freqs[i]
      if freq not in self.sequencer.dwell_history:
        continue

      dwell_completion_time = self.sequencer.dwell_history[freq]
      dwell_rect = [self.freq_coords[i] - self.dwell_pane_width/2, self.rect_dwell_display[1] + self.rect_dwell_display[3] * 0.33, self.dwell_pane_width, self.rect_dwell_display[3] * 0.33]
      dwell_color = self._color_interp(self.colors["dwell_new"], self.colors["dwell_old"], (now - dwell_completion_time) / self.dwell_scan_fade_time)
      pygame.draw.rect(self.surface, dwell_color, dwell_rect, 0)

    #
    #self.drfm_reports[freq][channel_index]["trigger_thresh"]
    for i in range(self.dwell_count):
      freq = self.dwell_freqs[i]

      for j in range(INTERCEPT_NUM_CHANNELS):
        report_count = self.drfm_reports[freq][j]
        if report_count["trigger_thresh"] > 0:
          trigger_color = self.colors["trigger_thresh"]
        elif report_count["trigger_forced"] > 0:
          trigger_color = self.colors["trigger_forced"]
        else:
          continue

        report_count["trigger_thresh"] = 0
        report_count["trigger_forced"] = 0

        trigger_coords = self.channel_coords[freq][j]
        #print("freq={} channel={} c={}".format(freq, j, trigger_coords))

        trigger_rect = [trigger_coords, self.rect_dwell_display[1] + self.rect_dwell_display[3] * 0.66, self.channel_width, self.rect_dwell_display[3] * 0.33]
        pygame.draw.rect(self.surface, trigger_color, trigger_rect, 0)

    for i in range(self.dwell_count - 1):
      pygame.draw.line(self.surface, self.colors["frame_elements"], [self.div_coords[i], self.rect_dwell_display[1]], [self.div_coords[i], self.rect_dwell_display[1] + self.rect_dwell_display[3] - 1], 1)

    pygame.draw.rect(self.surface, self.colors["frame_elements"], self.rect_dwell_display, 1)

  def render(self):
    self._render_waterfall_display()
    self._render_spectrum_display()
    self._render_cursor()

    pygame.draw.rect(self.surface, (0, 0, 255), [0, 0, 640, 800], 1)

  def update(self):
    #start = time.time()
    #self.pr.enable()

    self.spectrogram.set_thresholds(self.sequencer.threshold_control.get_thresholds_for_render())

    while len(self.sequencer.dwells_to_render) > 0:
      dwell = self.sequencer.dwells_to_render.pop(0)
      #self.pr.enable()
      self.spectrogram.process_new_dwell(dwell)

    self._update_frequency_range()

    #self.pr.disable()
    #s = io.StringIO()
    #sortby = SortKey.CUMULATIVE
    #ps = pstats.Stats(self.pr, stream=s).sort_stats(sortby)
    #ps.print_stats()
    #print(s.getvalue())
    #print("render_spectrum: {:.3f}".format(time.time() - start))

  def process_keydown(self, key):
    pass
    #if key in (pygame.K_TAB, pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT):
    #  self._update_zoom(key)
