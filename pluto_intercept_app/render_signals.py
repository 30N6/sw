import pygame
import time
import numpy as np
from pluto_intercept_hw_pkg import *
import turbo_colormap

class render_signals:

  def __init__(self, surface, sw_config, analysis_thread):
    self.surface          = surface
    self.sw_config        = sw_config
    self.analysis_thread  = analysis_thread

    self.colors = {}
    self.colors["border"]               = (0, 0, 255)
    self.colors["frame_elements"]       = (0, 128, 128)
    self.colors["grid_lines"]           = (0, 128, 128)
    self.colors["emitter_marker"]       = (0, 192, 0)
    self.colors["signal_entry_active"]  = (0, 255, 0)
    self.colors["signal_entry_stale"]   = (64, 128, 64)
    self.colors["signal_entry_tx"]      = (255, 64, 64)
    self.colors["emitter_histogram"]    = (192, 255, 0)

    self.colors["signal_entry_normal"]  = (0, 192, 192)
    self.colors["signal_entry_cw_spur"] = (128, 0, 0)


    self.font_main                      = pygame.font.SysFont('Consolas', 14)
    self.font_detail                    = pygame.font.SysFont('Consolas', 12)

    self.rect_frame_signals                       = [640, 384, 640, 384]

    self.rect_frame_signals_primary               = [640, 0,   384, 384]
    self.rect_frame_signals_tx                    = [1024,432, 256, 336]
    self.rect_frame_signals_primary_details       = [640, 192, 384, 192]
    self.rect_frame_signals_primary_plot_frame    = [641, 193, 382, 96]
    self.rect_frame_signals_primary_plot_image    = [642, 194, 380, 94]

    self.emitter_text_height            = 16
    self.emitter_stale_threshold        = 10

    self.signals                        = []
    self.max_rendered_signals           = 20

    self.last_update_time_confirmed     = 0
    self.max_rendered_signals_confirmed = 12
    self.max_rendered_signals_tx        = self.max_rendered_signals_confirmed
    self.selected_signal                = 0

    self.update_timeout_confirmed       = 1.0

  def _clamp_selected_emitters(self):
    if self.selected_signal >= self.max_rendered_signals_confirmed:
      self.selected_signal = self.max_rendered_signals_confirmed - 1
    if self.selected_signal >= len(self.signals_confirmed):
      self.selected_signal = len(self.signals_confirmed) - 1
    if self.selected_signal < 0:
      self.selected_signal = 0


  def _render_signal_list(self):
    emitter_entries = []
    index = 1
    for entry in self.signals:
      if index > self.max_rendered_signals:
        break

      signal_data = entry["signal_data"]

      power_mean_dB     = 10*np.log10(signal_data["power_mean"])
      power_max_dB      = 10*np.log10(signal_data["power_max"])
      signal_age        = min(99, round(entry["signal_age"]))
      update_age        = min(99, round(entry["update_age"]))
      report_count      = min(99, len(signal_data["reports"]))

      if signal_data["modulation"] == "CW?":
        signal_color = self.colors["signal_entry_cw_spur"]
      else:
        signal_color = self.colors["signal_entry_normal"]

      s = "{:2} {:3} {:1} {:8.3f} {:<12} {:4.1f} {:4.1f} {:>2.0f} {:>2} {:5.2f} {:4.1f} {:4} {:4.2f} {:5.3f}".format(index, signal_data["channel_index"], signal_data["stream_index"], signal_data["center_frequency"], signal_data["name"],
        power_mean_dB, power_max_dB, update_age, report_count, signal_data["bandwidth"] * 1e-3, signal_data["frequency_offset"] * 1e-3, signal_data["modulation"], signal_data["amplitude_iqr"], 0.999)
      pos_offset = [8, 16 + self.emitter_text_height * (index - 1)]

      emitter_entries.append({"str": s, "pos_offset": pos_offset, "color": signal_color})
      index += 1

    for entry in emitter_entries:
      text_data = self.font_main.render(entry["str"], True, entry["color"])
      text_rect = text_data.get_rect()
      text_rect.left = self.rect_frame_signals[0] + entry["pos_offset"][0]
      text_rect.bottom = self.rect_frame_signals[1] + entry["pos_offset"][1]
      self.surface.blit(text_data, text_rect)

  def render(self):
    pygame.draw.rect(self.surface, self.colors["border"], self.rect_frame_signals, 1)
    self._render_signal_list()

  def update(self):
    now = time.time()

    data = self.analysis_thread.get_tracked_signals()

    self.signals = []
    for entry in data:
      signal = {}
      signal["signal_data"]  = entry
      signal["signal_age"]   = now - entry["timestamp_initial"]
      signal["update_age"]   = now - entry["timestamp_final"]
      self.signals.append(signal)

    #self.signals.sort(key=lambda entry: entry["signal_data"]["center_frequency"], reverse=False)
    self.signals.sort(key=lambda entry: entry["signal_data"]["power_max"], reverse=True)

    #self._clamp_selected_emitters()

  def process_keydown(self, key):
    #if key not in (pygame.K_PAGEUP, pygame.K_PAGEDOWN):
    #  return
    #
    #if key == pygame.K_PAGEUP:
    #  self.selected_signal -= 1
    #elif key == pygame.K_PAGEDOWN:
    #  self.selected_signal += 1
    #
    #self._clamp_selected_emitters()
    pass
