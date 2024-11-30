import pygame
import time
from pluto_esm_hw_pkg import *
import numpy as np
import math

class render_emitters:

  def __init__(self, surface, sw_config, analysis_thread):
    self.surface          = surface
    self.sw_config        = sw_config
    self.analysis_thread  = analysis_thread

    self.colors = {}
    self.colors["border"] = (0, 0, 255)

    self.colors["frame_elements"] = (0, 128, 128)
    self.colors["grid_lines"] = (0, 128, 128)
    self.colors["zoom_marker"] = (0, 192, 192)

    self.colors["emitter_entry_active"] = (0, 255, 0)
    self.colors["emitter_entry_stale"]  = (64, 128, 64)

    self.font = pygame.font.SysFont('Consolas', 14)

    self.rect_frame_pulsed    = [640, 0,   384, 384]
    self.rect_frame_cw        = [640, 384, 384, 384]

    self.emitter_text_height      = 16
    self.emitter_stale_threshold  = 10


    self.emitters = []

  def render(self):
    pygame.draw.rect(self.surface, self.colors["border"], self.rect_frame_pulsed, 1)
    pygame.draw.rect(self.surface, self.colors["border"], self.rect_frame_cw, 1)

    emitter_entries = []
    index = 1
    for entry in self.emitters:
      if index > 12:
        break

      power_mean_dB     = 10*np.log10(entry["analysis_data"]["power_mean"])
      power_max_db      = 10*np.log10(entry["analysis_data"]["power_max"])
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
        power_mean_dB, power_max_db, emitter_age, update_age, pulses_in_window, mod_str)
      pos_offset = [8, 16 + self.emitter_text_height * (index - 1)]

      emitter_entries.append({"str": s, "pos_offset": pos_offset, "color": emitter_color})
      index += 1

    for entry in emitter_entries:
      text_data = self.font.render(entry["str"], True, entry["color"])
      text_rect = text_data.get_rect()
      text_rect.left = self.rect_frame_pulsed[0] + entry["pos_offset"][0]
      text_rect.bottom = self.rect_frame_pulsed[1] + entry["pos_offset"][1]
      self.surface.blit(text_data, text_rect)

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
