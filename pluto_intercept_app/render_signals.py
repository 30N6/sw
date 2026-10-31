import pygame
import time
import numpy as np
from pluto_intercept_hw_pkg import *
import turbo_colormap

class render_signals:

  def __init__(self, surface, sw_config, analysis_thread, audio_thread):
    self.surface          = surface
    self.sw_config        = sw_config
    self.analysis_thread  = analysis_thread
    self.audio_thread     = audio_thread

    self.colors = {}
    self.colors["border"]                       = (0, 0, 255)
    self.colors["frame_elements"]               = (0, 128, 128)
    self.colors["grid_lines"]                   = (0, 128, 128)

    self.colors["signal_entry_active"]          = (0, 255, 0)
    self.colors["signal_entry_stale"]           = (64, 128, 64)
    self.colors["signal_entry_tx"]              = (255, 64, 64)
    self.colors["emitter_histogram"]            = (192, 255, 0)

    self.colors["signal_entry_normal"]          = (0, 255, 64)
    self.colors["signal_entry_forced"]          = (0, 128, 128)
    self.colors["signal_entry_normal_cw_spur"]  = (192, 0, 0)
    self.colors["signal_entry_forced_cw_spur"]  = (128, 0, 0)

    self.colors["signal_marker_auto"]           = (224, 224, 0)
    self.colors["signal_marker_manual"]         = (0, 224, 224)

    self.font_main                              = pygame.font.SysFont('Consolas', 14)
    self.font_detail                            = pygame.font.SysFont('Consolas', 12)

    self.rect_frame_signals                     = [640, 384, 640, 384]
    self.rect_frame_signals_normal              = [640, 384, 640, 128]
    self.rect_frame_details                     = [640, 0,   384, 384]
    self.rect_frame_details_trace               = [672, 192, 256, 128]

    self.signal_text_height             = 16

    self.signals_normal                 = []
    self.signals_forced                 = []

    self.max_rendered_signals_normal    = 8
    self.max_rendered_signals_forced    = 16

    self.last_update_time_confirmed     = 0
    self.max_rendered_signals_confirmed = 12
    self.max_rendered_signals_tx        = self.max_rendered_signals_confirmed

    self.selected_index                 = 0
    self.selected_frequency             = 0
    self.selected_manual                = False
    self.audio_enabled                  = True
    self.last_audio_seq_num             = -1

    self.update_timeout_confirmed       = 1.0

  def _render_signal_list(self):
    emitter_entries = []

    index = 1
    for entry in self.signals_normal:
      if index > self.max_rendered_signals_normal:
        break

      signal_data = entry["signal_data"]

      power_mean_dB     = 10*np.log10(signal_data["power_mean"])
      power_max_dB      = 10*np.log10(signal_data["power_max"])
      signal_age        = min(99, round(entry["signal_age"]))
      update_age        = min(99, round(entry["update_age"]))
      report_count      = min(99, len(signal_data["reports"]))

      if signal_data["modulation"] == "CW?":
        signal_color = self.colors["signal_entry_normal_cw_spur"]
      else:
        signal_color = self.colors["signal_entry_normal"]

      s = "{:2} {:3} {:1} {:8.3f} {:<12} {:4.1f} {:4.1f} {:>3} {:>2} {:>2} {:5.2f} {:4.1f} {:4} {:4.2f} {:5.3f}".format(index, signal_data["channel_index"], signal_data["stream_index"], signal_data["center_frequency"], signal_data["name"],
        power_mean_dB, power_max_dB, signal_age, update_age, report_count, signal_data["bandwidth"] * 1e-3, signal_data["frequency_offset"] * 1e-3, signal_data["modulation"], signal_data["amplitude_iqr"], 0.999)

      pos_offset = [8, 16 + self.signal_text_height * (index - 1)]

      emitter_entries.append({"str": s, "pos_offset": pos_offset, "color": signal_color})
      index += 1

    if len(self.signals_normal) > 0:
      sel_x = self.rect_frame_signals_normal[0] + 2
      sel_y = self.rect_frame_signals_normal[1] + 8 + self.signal_text_height * self.selected_index
      sel_wh = 8

      if self.selected_manual:
        color = self.colors["signal_marker_manual"]
      else:
        color = self.colors["signal_marker_auto"]

      sel_points = [(sel_x,             sel_y - sel_wh/2),
                    (sel_x + sel_wh/2,  sel_y),
                    (sel_x,             sel_y + sel_wh/2)]
      pygame.draw.polygon(self.surface, color, sel_points)

    index = 1
    for entry in self.signals_forced:
      if index > self.max_rendered_signals_forced:
        break

      signal_data = entry["signal_data"]

      power_mean_dB     = 10*np.log10(signal_data["power_mean"])
      power_max_dB      = 10*np.log10(signal_data["power_max"])
      signal_age        = min(99, round(entry["signal_age"]))
      update_age        = min(99, round(entry["update_age"]))
      report_count      = min(99, len(signal_data["reports"]))

      if signal_data["modulation"] == "CW?":
        signal_color = self.colors["signal_entry_forced_cw_spur"]
      else:
        signal_color = self.colors["signal_entry_forced"]

      s = "{:2} {:3} {:1} {:8.3f} {:<12} {:4.1f} {:4.1f} {:>3} {:>2} {:>2} {:5.2f} {:4.1f} {:4} {:4.2f} {:5.3f}".format(index, signal_data["channel_index"], signal_data["stream_index"], signal_data["center_frequency"], signal_data["name"],
        power_mean_dB, power_max_dB, signal_age, update_age, report_count, signal_data["bandwidth"] * 1e-3, signal_data["frequency_offset"] * 1e-3, signal_data["modulation"], signal_data["amplitude_iqr"], 0.999)

      pos_offset = [8, 16 + self.signal_text_height * (self.max_rendered_signals_normal + index - 1)]

      emitter_entries.append({"str": s, "pos_offset": pos_offset, "color": signal_color})
      index += 1

    for entry in emitter_entries:
      text_data = self.font_main.render(entry["str"], True, entry["color"])
      text_rect = text_data.get_rect()
      text_rect.left = self.rect_frame_signals[0] + entry["pos_offset"][0]
      text_rect.bottom = self.rect_frame_signals[1] + entry["pos_offset"][1]
      self.surface.blit(text_data, text_rect)

  def _render_details(self):
    if not(self.signals_normal):
      return

    signal_entry    = self.signals_normal[self.selected_index]
    signal_data     = signal_entry["signal_data"]
    power_mean_dB   = 10*np.log10(signal_data["power_mean"])
    power_max_dB    = 10*np.log10(signal_data["power_max"])
    signal_age      = min(99, round(signal_entry["signal_age"]))
    update_age      = min(99, round(signal_entry["update_age"]))
    report_count    = min(99, len(signal_data["reports"]))

    lines = []
    lines.append("{:2} {:3} {:1} {:8.3f} {:<12}".format(self.selected_index, signal_data["channel_index"], signal_data["stream_index"], signal_data["center_frequency"], signal_data["name"]))
    lines.append("sig_age={:<3} upd_age={:<2} rpt_cnt={:<2}".format(signal_age, update_age, report_count))
    lines.append("pwr={:4.1f}/{:4.1f} BW={:5.2f} offs={:4.1f}".format(power_mean_dB, power_max_dB, signal_data["bandwidth"] * 1e-3, signal_data["frequency_offset"] * 1e-3))
    lines.append("mod={:4} amp_iqr={:4.2f} {:5.3f}".format(signal_data["modulation"], signal_data["amplitude_iqr"], 0.999))

    color = self.colors["signal_entry_normal"]

    for i in range(len(lines)):
      text_data = self.font_main.render(lines[i], True, color)
      text_rect = text_data.get_rect()
      text_rect.left = self.rect_frame_details[0] + 8
      text_rect.top = self.rect_frame_details[1] + self.signal_text_height * i
      self.surface.blit(text_data, text_rect)

    surf_s = pygame.surfarray.make_surface(signal_data["details"]["spectrum_trace"])
    self.surface.blit(surf_s, self.rect_frame_details_trace)

    pygame.draw.rect(self.surface, self.colors["border"], self.rect_frame_details_trace, 1)

    if self.audio_enabled:
      audio_text = "audio: ENABLED"
    else:
      audio_text = "audio: disabled"

    text_data = self.font_main.render(audio_text, True, color)
    text_rect = text_data.get_rect()
    text_rect.left = self.rect_frame_details[0] + 8
    text_rect.bottom = self.rect_frame_details[1] + self.rect_frame_details[3] - 2
    self.surface.blit(text_data, text_rect)

  def _update_signal_selection(self):
    if not(self.signals_normal):
      self.selected_index     = 0
      self.selected_frequency = 0
      self.selected_manual    = False

    elif self.selected_manual:
      freqs = [entry["signal_data"]["center_frequency"] for entry in self.signals_normal]
      if self.selected_frequency in freqs:
        self.selected_index = freqs.index(self.selected_frequency)
      else:
        self.selected_index     = 0
        self.selected_frequency = 0
        self.selected_manual    = False

    else:
      self.selected_index = 0
      self.selected_frequency = self.signals_normal[0]["signal_data"]["center_frequency"]

  def _update_audio(self):
    if not(self.signals_normal) or not(self.audio_enabled):
      return

    reports = self.signals_normal[self.selected_index]["signal_data"]["reports"]

    if self.last_audio_seq_num != reports[-1]["global_seq_num"]:
      for r in reports:
        if r["global_seq_num"] > self.last_audio_seq_num:
          self.audio_thread.submit_data(r)
          self.last_audio_seq_num = r["global_seq_num"]

  def render(self):
    pygame.draw.rect(self.surface, self.colors["border"], self.rect_frame_details, 1)
    pygame.draw.rect(self.surface, self.colors["border"], self.rect_frame_signals, 1)
    pygame.draw.rect(self.surface, self.colors["border"], self.rect_frame_signals_normal, 1)

    self._render_signal_list()
    self._render_details()

  def update(self):
    now = time.time()

    data = self.analysis_thread.get_tracked_signals()

    self.signals_normal = []
    self.signals_forced = []
    for entry in data:
      signal = {}
      signal["signal_data"]  = entry
      signal["signal_age"]   = now - entry["timestamp_initial"]
      signal["update_age"]   = now - entry["timestamp_final"]
      if entry["stream_index"] == (INTERCEPT_NUM_STREAMS - 1):
        self.signals_forced.append(signal)
      else:
        self.signals_normal.append(signal)

    #self.signals.sort(key=lambda entry: entry["signal_data"]["center_frequency"], reverse=False)
    self.signals_normal.sort(key=lambda entry: entry["signal_data"]["power_max"], reverse=True)
    self.signals_forced.sort(key=lambda entry: entry["signal_data"]["power_max"], reverse=True)

    self._update_signal_selection()
    self._update_audio()

    #self._clamp_selected_emitters()

  def process_keydown(self, key):
    if key not in (pygame.K_PAGEUP, pygame.K_PAGEDOWN, pygame.K_TAB):
      return

    selection_updated = False
    if key == pygame.K_PAGEUP:
      self.selected_index = max(self.selected_index - 1, 0)
      selection_updated = True
    elif key == pygame.K_PAGEDOWN:
      self.selected_index = min(min(self.selected_index + 1, len(self.signals_normal) - 1), self.max_rendered_signals_normal - 1)
      selection_updated = True

    if selection_updated:
      self.selected_manual = True
      self.selected_frequency = self.signals_normal[self.selected_index]["signal_data"]["center_frequency"]
      self._update_signal_selection()

    if key == pygame.K_TAB:
      if (self.signals_normal):
        self.audio_enabled = not(self.audio_enabled)
