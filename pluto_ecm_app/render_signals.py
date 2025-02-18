import pygame
import time
import numpy as np
from pluto_ecm_hw_pkg import *
import turbo_colormap

class render_signals:

  def __init__(self, surface, sw_config, analysis_thread, sequencer):
    self.surface          = surface
    self.sw_config        = sw_config
    self.analysis_thread  = analysis_thread
    self.ecm_controller   = sequencer.ecm_controller

    self.colors = {}
    self.colors["border"]               = (0, 0, 255)
    self.colors["frame_elements"]       = (0, 128, 128)
    self.colors["grid_lines"]           = (0, 128, 128)
    self.colors["emitter_marker"]       = (0, 192, 0)
    self.colors["signal_entry_active"]  = (0, 255, 0)
    self.colors["signal_entry_stale"]   = (64, 128, 64)
    self.colors["signal_entry_scan"]    = (0, 128, 192)
    self.colors["signal_entry_tx"]      = (255, 64, 64)
    self.colors["emitter_histogram"]    = (192, 255, 0)

    self.font_main                      = pygame.font.SysFont('Consolas', 14)
    self.font_detail                    = pygame.font.SysFont('Consolas', 12)

    self.rect_frame_signals_primary               = [640, 0,   384, 384]
    self.rect_frame_signals_secondary             = [640, 384, 384, 384]
    self.rect_frame_signals_tx                    = [1024,432, 256, 336]
    self.rect_frame_signals_primary_details       = [640, 192, 384, 192]
    self.rect_frame_signals_primary_plot_frame    = [641, 193, 382, 96]
    self.rect_frame_signals_primary_plot_image    = [642, 194, 380, 94]

    self.emitter_text_height            = 16
    self.emitter_stale_threshold        = 10

    self.signals_confirmed              = []
    self.signals_scan                   = []
    self.signals_tx                     = []
    self.last_update_time_confirmed     = 0
    self.max_rendered_signals_confirmed = 12
    self.max_rendered_signals_scan      = 20
    self.max_rendered_signals_tx        = self.max_rendered_signals_confirmed
    self.selected_signal                = 0

    self.update_timeout_confirmed       = 1.0

  def _render_confirmed_signal_list(self):
    emitter_entries = []
    index = 1
    for entry in self.signals_confirmed:
      if index > self.max_rendered_signals_confirmed:
        break

      signal_data = entry["signal_data"]
      stats = signal_data["stats"]

      power_mean_dB     = 10*np.log10(stats["power_mean"])
      power_max_dB      = 10*np.log10(stats["power_max"])
      signal_age        = min(99, round(entry["signal_age"]))
      update_age        = min(99, round(entry["update_age"]))
      report_count      = min(99, stats["report_count"])
      fit_metric        = stats["display_metric_mean"]

      if entry["update_age"] < self.emitter_stale_threshold:
        emitter_color = self.colors["signal_entry_active"]
      else:
        emitter_color = self.colors["signal_entry_stale"]

      s = "{:2} {:<10} {:6.1f} {:4.1f} {:4.1f} {:>2.0f} {:>2.0f} {:>2} {:5.3f}".format(index, signal_data["name"], signal_data["freq"],
        power_mean_dB, power_max_dB, signal_age, update_age, report_count, fit_metric)
      pos_offset = [8, 16 + self.emitter_text_height * (index - 1)]

      emitter_entries.append({"str": s, "pos_offset": pos_offset, "color": emitter_color})
      index += 1

    for entry in emitter_entries:
      text_data = self.font_main.render(entry["str"], True, entry["color"])
      text_rect = text_data.get_rect()
      text_rect.left = self.rect_frame_signals_primary[0] + entry["pos_offset"][0]
      text_rect.bottom = self.rect_frame_signals_primary[1] + entry["pos_offset"][1]
      self.surface.blit(text_data, text_rect)

    if len(self.signals_confirmed) > 0:
      sel_x = self.rect_frame_signals_primary[0] + 2
      sel_y = self.rect_frame_signals_primary[1] + 8 + self.emitter_text_height * self.selected_signal
      sel_wh = 8

      sel_points = [(sel_x,             sel_y - sel_wh/2),
                    (sel_x + sel_wh/2,  sel_y),
                    (sel_x,             sel_y + sel_wh/2)]
      pygame.draw.polygon(self.surface, self.colors["emitter_marker"], sel_points)

  def _render_scan_signal_list(self):
    emitter_entries = []
    index = 1
    for entry in self.signals_scan:
      if index > self.max_rendered_signals_scan:
        break

      signal_data = entry["signal_data"]
      stats = signal_data["stats"]

      power_mean_dB     = 10*np.log10(stats["power_mean"])
      power_max_dB      = 10*np.log10(stats["power_max"])
      signal_age        = min(99, round(entry["signal_age"]))
      update_age        = min(99, round(entry["update_age"]))
      report_count      = min(99, stats["report_count"])
      fit_metric        = stats["display_metric_mean"]
      emitter_color     = self.colors["signal_entry_scan"]

      s = "{:2} {:<10} {:6.1f} {:4.1f} {:4.1f} {:>2.0f} {:>2} {:5.3f}".format(index, signal_data["name"], signal_data["freq"],
        power_mean_dB, power_max_dB, update_age, report_count, fit_metric)
      pos_offset = [8, 16 + self.emitter_text_height * (index - 1)]

      emitter_entries.append({"str": s, "pos_offset": pos_offset, "color": emitter_color})
      index += 1

    for entry in emitter_entries:
      text_data = self.font_main.render(entry["str"], True, entry["color"])
      text_rect = text_data.get_rect()
      text_rect.left = self.rect_frame_signals_secondary[0] + entry["pos_offset"][0]
      text_rect.bottom = self.rect_frame_signals_secondary[1] + entry["pos_offset"][1]
      self.surface.blit(text_data, text_rect)

  def _render_tx_signal_list(self):
    emitter_entries = []
    index = 1
    for entry in self.signals_tx:
      if index > self.max_rendered_signals_tx:
        break

      signal_data   = entry["signal_data"]

      threshold_dB  = 10*np.log10(signal_data["threshold_level"])
      #signal_age    = min(99, round(entry["signal_age"]))
      tx_enabled    = "T" if signal_data["tx_enabled"] else ""
      emitter_color = self.colors["signal_entry_tx"]

      s = "{:2} {:<10} {:6.1f} {:4.1f} {:>2} {}".format(index, signal_data["name"], signal_data["freq"], threshold_dB, signal_data["threshold_shift"], tx_enabled)
      pos_offset = [8, 16 + self.emitter_text_height * (index - 1)]

      emitter_entries.append({"str": s, "pos_offset": pos_offset, "color": emitter_color})
      index += 1

    for entry in emitter_entries:
      text_data = self.font_main.render(entry["str"], True, entry["color"])
      text_rect = text_data.get_rect()
      text_rect.left = self.rect_frame_signals_tx[0] + entry["pos_offset"][0]
      text_rect.bottom = self.rect_frame_signals_tx[1] + entry["pos_offset"][1]
      self.surface.blit(text_data, text_rect)

  def _render_confirmed_details(self):
    pygame.draw.rect(self.surface, self.colors["border"], self.rect_frame_signals_primary_details, 1)
    pygame.draw.rect(self.surface, self.colors["frame_elements"], self.rect_frame_signals_primary_plot_frame, 1)

    if len(self.signals_confirmed) < (self.selected_signal + 1):
      return

    signal        = self.signals_confirmed[self.selected_signal]
    signal_data   = signal["signal_data"]
    stats         = signal_data["stats"]
    last_analysis = stats["last_analysis"]
    stft_data     = last_analysis["iq_stft_abs"]

    stft_max = np.max(stft_data)
    if stft_max != 0:
      stft_data = stft_data / stft_max

    surf_original = pygame.surfarray.make_surface(turbo_colormap.interpolate_color(stft_data))
    surf_scaled   = pygame.transform.scale(surf_original, (self.rect_frame_signals_primary_plot_image[2], self.rect_frame_signals_primary_plot_image[3]))
    self.surface.blit(surf_scaled, self.rect_frame_signals_primary_plot_image)

    power_mean_dB       = 10*np.log10(stats["power_mean"])
    power_max_dB        = 10*np.log10(stats["power_max"])
    duration_mean       = stats["duration_mean"]
    fft_mean_kHz        = stats["fft_mean"] / 1e3
    fft_std_kHz         = stats["fft_std"] / 1e3


    entries = []
    entries.append("{:<10} pwr_dB={:.1f}/{:.1f} len={:.1f}".format(signal_data["name"],
      power_mean_dB, power_max_dB, duration_mean))
    entries.append("fft_kHz={:.1f}/{:.1f}".format(fft_mean_kHz, fft_std_kHz))

    for i in range(len(entries)):
      entry           = entries[i]
      text_data       = self.font_detail.render(entry, True, self.colors["signal_entry_active"])
      text_rect       = text_data.get_rect()
      text_rect.left  = self.rect_frame_signals_primary_plot_frame[0] + 8
      text_rect.top   = self.rect_frame_signals_primary_plot_frame[1] + self.rect_frame_signals_primary_plot_frame[3] + 8 + 16 * i
      self.surface.blit(text_data, text_rect)


  #
  #  s = "{:<8} freq={:5.1f}".format(emitter["analysis_data"]["name"], emitter["analysis_data"]["freq"])
  #  entries.append({"str": s, "y_pos": self.rect_frame_signals_primary_plot_frame[1] + self.rect_frame_signals_primary_plot_frame[3] + 48 + 16 * 0})
  #
  #  s = "pwr={:3.1f}/{:3.1f} dB  PD={:3.1f}+/-{:3.1f} us".format(power_mean_dB, power_max_dB, pulse_duration_mean, pulse_duration_std)
  #  entries.append({"str": s, "y_pos": self.rect_frame_signals_primary_plot_frame[1] + self.rect_frame_signals_primary_plot_frame[3] + 48 + 16 * 1})
  #
  #  if mod_data is not None:
  #    s = "mod={}".format(mod_data["modulation_type"])
  #    if mod_data["modulation_type"] == "FM":
  #      s += "  N={}/{}  R^2={:<5.3f}  slope={:.1f} Hz/us".format(mod_data["pulses_with_mod"], mod_data["pulses_analyzed"],
  #        mod_data["FM_mean_r_squared"], mod_data["FM_mean_slope"])
  #    entries.append({"str": s, "y_pos": self.rect_frame_signals_primary_plot_frame[1] + self.rect_frame_signals_primary_plot_frame[3] + 48 + 16 * 2})
  #


  def _clamp_selected_emitters(self):
    if self.selected_signal >= self.max_rendered_signals_confirmed:
      self.selected_signal = self.max_rendered_signals_confirmed - 1
    if self.selected_signal >= len(self.signals_confirmed):
      self.selected_signal = len(self.signals_confirmed) - 1
    if self.selected_signal < 0:
      self.selected_signal = 0

  def render(self):
    pygame.draw.rect(self.surface, self.colors["border"], self.rect_frame_signals_primary, 1)
    pygame.draw.rect(self.surface, self.colors["border"], self.rect_frame_signals_secondary, 1)
    pygame.draw.rect(self.surface, self.colors["border"], self.rect_frame_signals_tx, 1)

    self._render_confirmed_signal_list()
    self._render_confirmed_details()
    self._render_scan_signal_list()
    self._render_tx_signal_list()

  def update(self):
    now = time.time()

    for entry in self.analysis_thread.data_to_render:
      if "confirmed_signals" in entry:
        self.last_update_time_confirmed = now
        self.signals_confirmed = []

        for signal_data in entry["confirmed_signals"]:
          signal = {}
          signal["signal_data"]  = signal_data
          signal["signal_age"]   = now - signal_data["timestamp_initial"]
          signal["update_age"]   = now - signal_data["timestamp_final"]
          self.signals_confirmed.append(signal)

      elif "scan_signals" in entry:
        self.signals_scan = []
        for signal_data in entry["scan_signals"]:
          signal = {}
          signal["signal_data"]  = signal_data
          signal["signal_age"]   = now - signal_data["timestamp_initial"]
          signal["update_age"]   = now - signal_data["timestamp_final"]
          self.signals_scan.append(signal)

      else:
        raise RuntimeError("unexpected data")

    self.signals_tx = []
    for signal_data in self.ecm_controller.signals_for_tx:
      signal = {}
      signal["signal_data"] = signal_data
      signal["signal_age"] = now - signal_data["timestamp"]
      self.signals_tx.append(signal)

    if (now - self.last_update_time_confirmed) > self.update_timeout_confirmed:
      self.signals_confirmed = []

    self.analysis_thread.data_to_render = []
    self.signals_confirmed.sort(key=lambda entry: entry["signal_data"]["stats"]["power_mean"], reverse=True)
    self.signals_tx.sort(key=lambda entry: entry["signal_data"]["freq"], reverse=False)

    self._clamp_selected_emitters()

  def process_keydown(self, key):
    if key not in (pygame.K_PAGEUP, pygame.K_PAGEDOWN):
      return

    if key == pygame.K_PAGEUP:
      self.selected_signal -= 1
    elif key == pygame.K_PAGEDOWN:
      self.selected_signal += 1

    self._clamp_selected_emitters()
