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

    self.graphics_left            = 64
    self.graphics_width           = 512

    self.rect_waterfall           = [self.graphics_left, 28,    self.graphics_width, 320]
    self.rect_spectrum            = [self.graphics_left, 368,   self.graphics_width, 128]

    self.surf_waterfall           = pygame.Surface((self.graphics_width, self.rect_waterfall[3]))
    self.surf_spectrum            = pygame.Surface((self.graphics_width, self.rect_spectrum[3]))
    self.dirty_waterfall          = True
    self.dirty_spectrum           = True

    self.surface                  = surface
    self.sw_config                = sw_config
    self.sequencer                = sequencer
    self.spectrogram              = pluto_intercept_spectrogram.pluto_intercept_spectrogram(self.graphics_width, self.rect_waterfall[3], self.rect_spectrum[3])

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

    self.colors["trigger_normal"] = (0, 192, 192)
    self.colors["trigger_coast"]  = (192, 192, 0)
    self.colors["trigger_forced"] = (0, 64, 192)
    self.trigger_type_to_color    = [self.colors["trigger_normal"], self.colors["trigger_coast"], self.colors["trigger_forced"]]

    self.font_main                = pygame.font.SysFont('Consolas', 16)
    self.font_detail              = pygame.font.SysFont('Consolas', 12)

    self._update_frequency_range()


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

    self.frequency_range_labels = []
    for f in self.frequency_range:
      freq_str = "{:.3f}".format(f)
      self.frequency_range_labels.append(self.font_main.render(freq_str, True, self.colors["frame_elements"]))

    self.channel_frequency_labels = []
    for trigger_type in range(len(self.trigger_type_to_color)):
      current_labels = []
      for i in range(INTERCEPT_NUM_CHANNELS):
        current_labels.append(self.font_main.render(self.sequencer.get_channel_frequency_str(i), True, self.trigger_type_to_color[trigger_type]))
      self.channel_frequency_labels.append(current_labels)

  def _render_waterfall_display(self):
    if self.dirty_waterfall:
      pygame.surfarray.blit_array(self.surf_waterfall, self.spectrogram.get_waterfall(False))
      self.dirty_waterfall = False
    self.surface.blit(self.surf_waterfall, self.rect_waterfall)

    #TODO: pre-compute
    freq_x = [self.rect_waterfall[0], self.rect_waterfall[0] + self.rect_waterfall[2] // 2, self.rect_waterfall[0] + self.rect_waterfall[2]]

    for i in range(len(freq_x)):
      text_data = self.frequency_range_labels[i]
      text_rect = text_data.get_rect()
      text_rect.centerx = freq_x[i]
      text_rect.centery = self.rect_waterfall[1] - 16
      self.surface.blit(text_data, text_rect)

    pygame.draw.rect(self.surface, self.colors["frame_elements"], self.rect_waterfall, 1)

  def _render_spectrum_display(self):
    if self.dirty_spectrum:
      pygame.surfarray.blit_array(self.surf_spectrum, self.spectrogram.get_trace())
      self.dirty_spectrum = False
    self.surface.blit(self.surf_spectrum, self.rect_spectrum)

    for stream_index in range(INTERCEPT_NUM_STREAMS):
      trigger_type, channel_index, sample_index = self.sequencer.get_stream_state(stream_index)
      frequency_str = self.sequencer.get_channel_frequency_str(channel_index)

      if trigger_type > 2:
        continue

      line_x = self.rect_spectrum[0] + channel_index
      line_y = [self.rect_spectrum[1] + self.rect_spectrum[3] * 0.75, self.rect_spectrum[1] + self.rect_spectrum[3]]
      line_color = self.trigger_type_to_color[trigger_type]
      pygame.draw.line(self.surface, line_color, [line_x, line_y[0]], [line_x, line_y[1]], 1)
      #trigger_type_to_color

      text_data = self.channel_frequency_labels[trigger_type][channel_index]
      text_rect = text_data.get_rect()
      text_rect.centerx = line_x
      text_rect.top = line_y[1] + 4
      self.surface.blit(text_data, text_rect)

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

      x_text = self.graphics_left + self.graphics_width + 4;
      freq = self.frequency_range[0] + x_frac * (self.frequency_range[2] - self.frequency_range[0])

      s = "{:<.3f}".format(freq)
      text_data = self.font_detail.render(s, True, self.colors["frame_elements"])
      text_rect = text_data.get_rect()
      text_rect.left = x_text
      text_rect.bottom = y_text
      self.surface.blit(text_data, text_rect)

  def render(self):
    self._render_waterfall_display()
    self._render_spectrum_display()
    self._render_cursor()

    pygame.draw.rect(self.surface, (0, 0, 255), [0, 0, 640, 800], 1)

  def update(self):
    #start = time.time()
    #self.pr.enable()

    thresholds = self.sequencer.threshold_control.get_thresholds_for_render()
    if thresholds is not None:
      self.spectrogram.set_thresholds(thresholds)

    if self.sequencer.dwells_to_render:
      self.dirty_waterfall = True
      self.dirty_spectrum = True

      for dwell in self.sequencer.dwells_to_render:
        self.spectrogram.process_new_dwell(dwell)
      self.sequencer.dwells_to_render.clear()

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
