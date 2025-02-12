import pygame
import time
from pluto_ecm_hw_pkg import *
import pluto_ecm_spectrogram
import numpy as np
import math

import cProfile, pstats, io
from pstats import SortKey

class render_spectrum:

  def __init__(self, surface, sw_config, sequencer):
    self.rect_width                       = 600
    self.rect_left                        = 24
    self.rect_dwell_display               = [self.rect_left, 4,   self.rect_width, 16]
    self.rect_spectrum_display_primary    = [self.rect_left, 56,  self.rect_width, 320]
    self.rect_spectrum_display_secondary  = [self.rect_left, 400, self.rect_width, 288]

    self.dwell_count      = len(sw_config.config["dwell_config"]["dwell_freqs"])
    self.dwell_freqs      = [d["freq"] for d in sw_config.config["dwell_config"]["dwell_freqs"]]
    self.dwell_pane_width = self.rect_width/self.dwell_count
    if self.dwell_count > 1:
      self.div_coords = [self.rect_left + self.dwell_pane_width * i for i in range(1, self.dwell_count)]
    else:
      self.div_coords = []
    self.freq_coords = [self.rect_left + self.dwell_pane_width * (i + 0.5) for i in range(self.dwell_count)]

    self.surface    = surface
    self.sw_config  = sw_config
    self.sequencer  = sequencer

    self.spectrogram = {}
    for freq in self.dwell_freqs:
      self.spectrogram[freq] = pluto_ecm_spectrogram.pluto_ecm_spectrogram(self.sw_config, freq, self.dwell_pane_width,
        self.rect_spectrum_display_primary[3], self.rect_spectrum_display_secondary[3],
        self.sequencer.ecm_controller.dwell_trigger_thresholds, self.sequencer.ecm_controller.map_tag_to_state)

    self.colors = {}
    self.colors["cal_old"]        = (192, 0, 0)
    self.colors["cal_new"]        = (0, 192, 0)
    self.colors["dwell_old"]      = (64, 0, 0)
    self.colors["dwell_new"]      = (0, 255, 0)
    self.colors["frame_elements"] = (0, 128, 128)
    self.colors["grid_lines"]     = (0, 128, 128)
    self.colors["zoom_marker"]    = (0, 192, 192)

    self.dwell_cal_interval   = sw_config.config["fast_lock_config"]["recalibration_interval"]

    self.dwell_cal_height     = 0.5
    self.dwell_scan_height    = 1 - self.dwell_cal_height
    self.dwell_scan_fade_time = 0.5

    self.font = pygame.font.SysFont('Consolas', 12)

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

  def _render_dwell_display(self):
    now           = time.time()

    #mhz_per_px    = self.max_freq / self.rect_dwell_display[2]
    #px_per_dwell  = math.ceil(self.dwell_bw / mhz_per_px)

    # calibration status
    for i in range(len(self.sequencer.fast_lock_cal_state)):
      cal_state = self.sequencer.fast_lock_cal_state[i]
      dwell_rect = [self.freq_coords[i] - self.dwell_pane_width/2, self.rect_dwell_display[1], self.dwell_pane_width, self.rect_dwell_display[3] * self.dwell_cal_height]

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
      dwell_rect = [self.freq_coords[i] - self.dwell_pane_width/2, self.rect_dwell_display[1] + self.rect_dwell_display[3] * (1 - self.dwell_scan_height), self.dwell_pane_width, self.rect_dwell_display[3] * self.dwell_scan_height]
      dwell_color = self._color_interp(self.colors["dwell_new"], self.colors["dwell_old"], (now - dwell_completion_time) / self.dwell_scan_fade_time)
      pygame.draw.rect(self.surface, dwell_color, dwell_rect, 0)

    for i in range(self.dwell_count - 1):
      pygame.draw.line(self.surface, self.colors["frame_elements"], [self.div_coords[i], self.rect_dwell_display[1]], [self.div_coords[i], self.rect_dwell_display[1] + self.rect_dwell_display[3] - 1], 1)

    pygame.draw.rect(self.surface, self.colors["frame_elements"], self.rect_dwell_display, 1)

  def _render_spectrum_display(self):
    for i in range(self.dwell_count):
      freq = self.dwell_freqs[i]

      freq_str = "{:.1f}".format(freq)
      text_data = self.font.render(freq_str, True, self.colors["frame_elements"])
      text_rect = text_data.get_rect()
      text_rect.centerx = self.freq_coords[i]
      text_rect.centery = self.rect_spectrum_display_primary[1] - 12
      self.surface.blit(text_data, text_rect)

      data_primary = self.spectrogram[freq].get_spectrogram(False)
      surf_primary = pygame.surfarray.make_surface(data_primary)
      rect_primary = [self.freq_coords[i] - data_primary.shape[0]/2, self.rect_spectrum_display_primary[1], data_primary.shape[0], self.rect_spectrum_display_primary[3]]
      self.surface.blit(surf_primary, rect_primary)

      data_secondary = self.spectrogram[freq].get_spectrum_trace()
      surf_secondary = pygame.surfarray.make_surface(data_secondary)
      rect_secondary = [self.freq_coords[i] - data_secondary.shape[0]/2, self.rect_spectrum_display_secondary[1], data_secondary.shape[0], self.rect_spectrum_display_secondary[3]]
      self.surface.blit(surf_secondary, rect_secondary)

    for i in range(self.dwell_count - 1):
      pygame.draw.line(self.surface, self.colors["frame_elements"], [self.div_coords[i], self.rect_spectrum_display_primary[1]],   [self.div_coords[i], self.rect_spectrum_display_primary[1] + self.rect_spectrum_display_primary[3] - 1],     1)
      pygame.draw.line(self.surface, self.colors["frame_elements"], [self.div_coords[i], self.rect_spectrum_display_secondary[1]], [self.div_coords[i], self.rect_spectrum_display_secondary[1] + self.rect_spectrum_display_secondary[3] - 1], 1)

    pygame.draw.rect(self.surface, self.colors["frame_elements"], self.rect_spectrum_display_primary, 1)
    pygame.draw.rect(self.surface, self.colors["frame_elements"], self.rect_spectrum_display_secondary, 1)

    #TODO
    #graph_rects = [self.rect_spectrum_display_primary, self.rect_spectrum_display_secondary]
    #
    #freq_tick_height = 6
    #freq_tick_count = 7
    #for i in range(freq_tick_count):
    #  tick_frac = (i / (freq_tick_count - 1))
    #  freq_str = "{}".format(round(self.freq_zoom_range[0] + tick_frac * (self.freq_zoom_range[1] - self.freq_zoom_range[0])))
    #  text_data = self.font.render(freq_str, True, self.colors["frame_elements"])
    #
    #  for j in range(len(graph_rects)):
    #    x = graph_rects[j][0] + tick_frac * (graph_rects[j][2] - 1)
    #
    #    pos_start = (x, graph_rects[j][1])
    #    pos_end   = (x, graph_rects[j][1] - freq_tick_height)
    #    pygame.draw.line(self.surface, self.colors["frame_elements"], pos_start, pos_end)
    #
    #    text_rect = text_data.get_rect()
    #    text_rect.centerx = x
    #    text_rect.bottom = graph_rects[j][1] - freq_tick_height - 1
    #    self.surface.blit(text_data, text_rect)
    #
    power_label_count = 7
    spec_0 = self.spectrogram[self.dwell_freqs[0]]
    for i in range(power_label_count):
      power_frac = (i / (power_label_count - 1))
      freq_str = "{}".format(round(spec_0.spec_trace_min_dB + power_frac * (spec_0.spec_trace_max_dB - spec_0.spec_trace_min_dB)))
      text_data = self.font.render(freq_str, True, self.colors["frame_elements"])
      text_data = pygame.transform.rotate(text_data, 90)

      text_rect = text_data.get_rect()
      text_rect.left = self.rect_spectrum_display_secondary[0] - 12
      text_rect.centery = self.rect_spectrum_display_secondary[1] + self.rect_spectrum_display_secondary[3] * (1 - power_frac)
      self.surface.blit(text_data, text_rect)
    #
    #peaks       = [self._get_spectrum_peaks(self.spectrogram.last_buffer_avg,  3, [spec_zoom_i_start, spec_zoom_i_stop], spec_mhz_per_px, True),
    #               self._get_spectrum_peaks(self.spectrogram.last_buffer_peak, 3, [spec_zoom_i_start, spec_zoom_i_stop], spec_mhz_per_px, True)]
    #status_str  = ["[AVERAGE] peak_val_dB={:<18} peak_freq={:<24}",
    #               "[PEAK]    peak_val_dB={:<18} peak_freq={:<24}"]
    #
    #for i in range(len(peaks)):
    #  peak_values = "[" + " ".join(["{:4.1f}".format(v) for v in peaks[i][1]]) + "]"
    #  peak_freqs = "[" + " ".join(["{:6.1f}".format(v) for v in peaks[i][0]]) + "]"
    #
    #  s = status_str[i].format(peak_values, peak_freqs)
    #  text_data = self.font.render(s, True, self.colors["frame_elements"])
    #  text_rect = text_data.get_rect()
    #  text_rect.left = graph_rects[1][0]
    #  text_rect.bottom = graph_rects[1][1] + graph_rects[i][3] + 16 * i
    #  self.surface.blit(text_data, text_rect)
    #
    #cursor_pos          = pygame.mouse.get_pos()
    #cursor_in_primary   = self._check_inside_rect(cursor_pos, self.rect_spectrum_display_primary)
    #cursor_in_secondary = self._check_inside_rect(cursor_pos, self.rect_spectrum_display_secondary)
    #if cursor_in_primary or cursor_in_secondary:
    #  if cursor_in_primary:
    #    x_frac = (cursor_pos[0] - self.rect_spectrum_display_primary[0]) / self.rect_spectrum_display_primary[2]
    #  else:
    #    x_frac = (cursor_pos[0] - self.rect_spectrum_display_secondary[0]) / self.rect_spectrum_display_secondary[2]
    #
    #  freq = self.freq_zoom_range[0] + x_frac * (self.freq_zoom_range[1] - self.freq_zoom_range[0])
    #  s = "[CURSOR]: freq={:<.1f}".format(freq)
    #  text_data = self.font.render(s, True, self.colors["frame_elements"])
    #  text_rect = text_data.get_rect()
    #  text_rect.left = graph_rects[1][0]
    #  text_rect.bottom = graph_rects[1][1] + graph_rects[i][3] + 16 * 3
    #  self.surface.blit(text_data, text_rect)

  def render(self):
    self._render_dwell_display()
    self._render_spectrum_display()

    pygame.draw.rect(self.surface, (0, 0, 255), [0, 0, 640, 768], 1)

  def update(self):
    #self.pr.enable()

    while len(self.sequencer.dwell_rows_to_render) > 0:
      self.sequencer.dwell_rows_to_render.pop(0)
      #self.pr.enable()
      for freq in self.dwell_freqs:
        self.spectrogram[freq].process_new_row(self.sequencer.dwell_buffer)

      #self.pr.disable()
      #s = io.StringIO()
      #sortby = SortKey.CUMULATIVE
      #ps = pstats.Stats(self.pr, stream=s).sort_stats(sortby)
      #ps.print_stats()
      #print(s.getvalue())

  def process_keydown(self, key):
    pass
    #if key in (pygame.K_TAB, pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT):
    #  self._update_zoom(key)
