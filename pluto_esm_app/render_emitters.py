import pygame
import time
import numpy as np
import pluto_esm_pulsed_emitter_plotter
from pluto_esm_hw_pkg import *

class render_emitters:

  def __init__(self, surface, sw_config, analysis_thread):
    self.surface          = surface
    self.sw_config        = sw_config
    self.analysis_thread  = analysis_thread

    self.colors = {}
    self.colors["border"]               = (0, 0, 255)
    self.colors["frame_elements"]       = (0, 128, 128)
    self.colors["grid_lines"]           = (0, 128, 128)
    self.colors["emitter_marker"]       = (0, 192, 0)
    self.colors["emitter_entry_active"] = (0, 255, 0)
    self.colors["emitter_entry_stale"]  = (64, 128, 64)
    self.colors["emitter_histogram"]    = (192, 255, 0)

    self.font_main    = pygame.font.SysFont('Consolas', 14)
    self.font_detail  = pygame.font.SysFont('Consolas', 12)

    self.rect_frame_pulsed            = [640, 0,   384, 384]
    self.rect_frame_cw                = [640, 384, 384, 384]
    self.rect_frame_pulsed_details    = [640, 192, 384, 192]
    self.rect_frame_pulsed_plot_frame = [648, 200, 368, 96]
    self.rect_frame_pulsed_plot_image = [649, 201, 366, 94]

    self.emitter_text_height      = 16
    self.emitter_stale_threshold  = 10

    self.emitters = []
    self.selected_emitter = 0

    self.pri_plot = pluto_esm_pulsed_emitter_plotter.pluto_esm_pulsed_emitter_plotter(self.rect_frame_pulsed_plot_image[2:4])

  def _render_pulsed_emitter_list(self):
    emitter_entries = []
    index = 1
    for entry in self.emitters:
      if index > 12:
        break

      power_mean_dB     = 10*np.log10(entry["analysis_data"]["power_mean"])
      power_max_dB      = 10*np.log10(entry["analysis_data"]["power_max"])
      emitter_age       = min(999, round(entry["emitter_age"]))
      update_age        = min(99, round(entry["update_age"]))
      pulses_in_window  = min(9999, entry["analysis_data"]["pulses_in_window"])

      if entry["analysis_data"]["modulation"] is not None:
        mod_str = entry["analysis_data"]["modulation"]["modulation_type"]
      else:
        mod_str = ""

      if entry["update_age"] < self.emitter_stale_threshold:
        emitter_color = self.colors["emitter_entry_active"]
      else:
        emitter_color = self.colors["emitter_entry_stale"]

      s = "{:2} {:<8} {:5.1f}  {:3.1f} {:3.1f}  {:3.0f} {:>2.0f} {:>4} {:>3}".format(index, entry["analysis_data"]["name"], entry["analysis_data"]["freq"],
        power_mean_dB, power_max_dB, emitter_age, update_age, pulses_in_window, mod_str)
      pos_offset = [8, 16 + self.emitter_text_height * (index - 1)]

      emitter_entries.append({"str": s, "pos_offset": pos_offset, "color": emitter_color})
      index += 1

    for entry in emitter_entries:
      text_data = self.font_main.render(entry["str"], True, entry["color"])
      text_rect = text_data.get_rect()
      text_rect.left = self.rect_frame_pulsed[0] + entry["pos_offset"][0]
      text_rect.bottom = self.rect_frame_pulsed[1] + entry["pos_offset"][1]
      self.surface.blit(text_data, text_rect)

    if len(self.emitters) > 0:
      sel_x = self.rect_frame_pulsed[0] + 2
      sel_y = self.rect_frame_pulsed[1] + 8 + self.emitter_text_height * self.selected_emitter
      sel_wh = 8

      sel_points = [(sel_x,             sel_y - sel_wh/2),
                    (sel_x + sel_wh/2,  sel_y),
                    (sel_x,             sel_y + sel_wh/2)]
      pygame.draw.polygon(self.surface, self.colors["emitter_marker"], sel_points)

  def _render_pulsed_emitter_details(self):
    pygame.draw.rect(self.surface, self.colors["border"], self.rect_frame_pulsed_details, 1)
    pygame.draw.rect(self.surface, self.colors["frame_elements"], self.rect_frame_pulsed_plot_frame, 1)

    if len(self.emitters) < (self.selected_emitter + 1):
      return

    emitter = self.emitters[self.selected_emitter]
    hist_image, max_pri = emitter["histogram_pri"]

    surf = pygame.surfarray.make_surface(hist_image)
    self.surface.blit(surf, self.rect_frame_pulsed_plot_image)

    pri_label_count = 9
    for i in range(pri_label_count):
      pri_frac = (i / (pri_label_count - 1))
      pri_str = "{}".format(round(pri_frac * max_pri))
      if i == 0:
        pri_str += " us"
      text_data = self.font_detail.render(pri_str, True, self.colors["frame_elements"])
      text_data = pygame.transform.rotate(text_data, -90)

      text_rect = text_data.get_rect()
      text_rect.centerx = self.rect_frame_pulsed_plot_frame[0] + self.rect_frame_pulsed_plot_frame[2] * pri_frac
      text_rect.top = self.rect_frame_pulsed_plot_frame[1] + self.rect_frame_pulsed_plot_frame[3]
      self.surface.blit(text_data, text_rect)

    power_mean_dB       = 10*np.log10(emitter["analysis_data"]["power_mean"])
    power_max_dB        = 10*np.log10(emitter["analysis_data"]["power_max"])
    pulse_duration_mean = emitter["analysis_data"]["pulse_duration_mean"]
    pulse_duration_std  = emitter["analysis_data"]["pulse_duration_std"]
    mod_data            = emitter["analysis_data"]["modulation"]
    entries = []

    s = "{:<8} freq={:5.1f}".format(emitter["analysis_data"]["name"], emitter["analysis_data"]["freq"])
    entries.append({"str": s, "y_pos": self.rect_frame_pulsed_plot_frame[1] + self.rect_frame_pulsed_plot_frame[3] + 48 + 16 * 0})

    s = "pwr={:3.1f}/{:3.1f} dB  PD={:3.1f}+/-{:3.1f} us".format(power_mean_dB, power_max_dB, pulse_duration_mean, pulse_duration_std)
    entries.append({"str": s, "y_pos": self.rect_frame_pulsed_plot_frame[1] + self.rect_frame_pulsed_plot_frame[3] + 48 + 16 * 1})

    if mod_data is not None:
      s = "mod={}".format(mod_data["modulation_type"])
      if mod_data["modulation_type"] == "FM":
        s += "  N={}/{}  R^2={:<5.3f}  slope={:.1f} Hz/us".format(mod_data["pulses_with_mod"], mod_data["pulses_analyzed"],
          mod_data["FM_mean_r_squared"], mod_data["FM_mean_slope"])
      entries.append({"str": s, "y_pos": self.rect_frame_pulsed_plot_frame[1] + self.rect_frame_pulsed_plot_frame[3] + 48 + 16 * 2})

    for entry in entries:
      text_data = self.font_detail.render(entry["str"], True, self.colors["emitter_entry_active"])
      text_rect = text_data.get_rect()
      text_rect.left = self.rect_frame_pulsed_plot_frame[0]
      text_rect.bottom = entry["y_pos"]
      self.surface.blit(text_data, text_rect)

  def _clamp_selected_emitter(self):
    if self.selected_emitter >= len(self.emitters):
      self.selected_emitter = len(self.emitters) - 1
    if self.selected_emitter < 0:
      self.selected_emitter = 0

  def render(self):
    pygame.draw.rect(self.surface, self.colors["border"], self.rect_frame_pulsed, 1)
    pygame.draw.rect(self.surface, self.colors["border"], self.rect_frame_cw, 1)

    self._render_pulsed_emitter_list()
    self._render_pulsed_emitter_details()

  def update(self):
    if len(self.analysis_thread.output_data_to_render) == 0:
      return

    now = time.time()

    for entry in self.analysis_thread.output_data_to_render:
      if "pulsed_emitters" not in entry:
        continue

      self.emitters = []
      for analysis_data in entry["pulsed_emitters"]:
        emitter = {}
        emitter["analysis_data"]  = analysis_data
        emitter["emitter_age"]    = now - analysis_data["pdw_time_initial"]
        emitter["update_age"]     = now - analysis_data["pdw_time_final"]
        self.emitters.append(emitter)

    self.analysis_thread.output_data_to_render = []
    self.emitters.sort(key=lambda entry: entry["analysis_data"]["power_mean"], reverse=True)

    for emitter in self.emitters:
      emitter["histogram_pri"] = self.pri_plot.get_pri_plot(emitter["analysis_data"]["sorted_pulse_pri"], self.colors["emitter_histogram"])

  def process_keydown(self, key):
    if key not in (pygame.K_f, pygame.K_v):
      return

    if key == pygame.K_f:
      self.selected_emitter -= 1
    elif key == pygame.K_v:
      self.selected_emitter += 1

    self._clamp_selected_emitter()
