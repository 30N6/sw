import pygame
import time
import numpy as np
from pluto_intercept_hw_pkg import *
import turbo_colormap

import cProfile, pstats, io
from pstats import SortKey

class render_streams:

  def __init__(self, surface, sw_config, analysis_thread, sequencer):
    self.surface          = surface
    self.sw_config        = sw_config
    self.analysis_thread  = analysis_thread
    self.sequencer        = sequencer
    #self.ecm_controller   = sequencer.ecm_controller

    self.graphics_left                    = 64
    self.graphics_width                   = 512

    self.rect_stream                      = [self.graphics_left, 536,   self.graphics_width, 272]
    self.stream_rows                      = 2
    self.stream_cols                      = INTERCEPT_NUM_STREAMS // self.stream_rows
    self.stream_box_height                = 96
    self.stream_box_width                 = self.graphics_width // self.stream_cols

    self.stream_trace_max_dB              = 30
    self.stream_trace_min_dB              = -60

    self.stream_box_data                  = [None for i in range(INTERCEPT_NUM_STREAMS)]

    assert (self.stream_rows * self.stream_cols == INTERCEPT_NUM_STREAMS)

    self.trigger_type_map = ("N", "C", "F", " ")

    self.colors = {}
    self.colors["border"]               = (0, 0, 255)
    self.colors["frame_elements"]       = (0, 255, 192)
    self.colors["grid_lines"]           = (0, 128, 128)
    self.colors["emitter_marker"]       = (0, 192, 0)
    self.colors["signal_entry_active"]  = (0, 255, 0)
    self.colors["signal_entry_stale"]   = (64, 128, 64)
    self.colors["signal_entry_scan"]    = (0, 128, 192)
    self.colors["signal_entry_tx"]      = (255, 64, 64)
    self.colors["emitter_histogram"]    = (192, 255, 0)

    self.colors["trace_peak"]           = np.asarray([32, 255, 32])

    self.font_main                      = pygame.font.SysFont('Consolas', 16)
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

    self._update_labels()

    self.pr = cProfile.Profile()

  def _update_labels(self):
    self.channel_frequency_label = []
    for i in range(INTERCEPT_NUM_CHANNELS):
      frequency_str = self.sequencer.get_channel_frequency_str(i)
      self.channel_frequency_label.append(self.font_main.render(frequency_str, True, self.colors["frame_elements"]))

    self.trigger_type_label = []
    for i in range(len(self.trigger_type_map)):
      self.trigger_type_label.append(self.font_main.render(self.trigger_type_map[i], True, self.colors["frame_elements"]))

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

  def _render_stream_display(self):
    for i_row in range(self.stream_rows):
      for i_col in range(self.stream_cols):
        stream_index = i_row * self.stream_cols + i_col

        rect_x = i_col * (self.graphics_width // self.stream_cols) + self.graphics_left
        rect_y = i_row * (self.rect_stream[3] // self.stream_rows) + self.rect_stream[1]
        rect = [rect_x, rect_y, self.stream_box_width, self.stream_box_height]

        trigger_type, channel_index, sample_index = self.sequencer.get_stream_state(stream_index)
        frequency_str = self.sequencer.get_channel_frequency_str(channel_index)

        if trigger_type > 2:
          pygame.draw.line(self.surface, self.colors["frame_elements"], [rect_x, rect_y], [rect_x + self.stream_box_width, rect_y + self.stream_box_height], 1)
          pygame.draw.line(self.surface, self.colors["frame_elements"], [rect_x + self.stream_box_width, rect_y], [rect_x, rect_y + self.stream_box_height], 1)
        else:
          text_data = self.trigger_type_label[trigger_type]
          text_rect = text_data.get_rect()
          text_rect.left = rect_x + 4 #+ self.stream_box_width / 2
          text_rect.centery = rect_y - 8 #+ self.stream_box_height + 12
          self.surface.blit(text_data, text_rect)

          text_data = self.channel_frequency_label[channel_index]
          text_rect = text_data.get_rect()
          text_rect.centerx = rect_x + self.stream_box_width / 2
          text_rect.centery = rect_y - 8
          self.surface.blit(text_data, text_rect)

          text_data = self.font_main.render("{}".format(sample_index), True, self.colors["frame_elements"])
          text_rect = text_data.get_rect()
          text_rect.right = rect_x + self.stream_box_width
          text_rect.centery = rect_y + self.stream_box_height + 8
          self.surface.blit(text_data, text_rect)

          data_s = self.stream_box_data[stream_index]
          if data_s is not None:
            data_max = np.max(data_s)
            if data_max > 0:
              data_s_normalized = data_s * (255.0 / data_max)
            else:
              data_s_normalized = data_s
            surf_s = pygame.surfarray.make_surface(data_s_normalized)
            self.surface.blit(surf_s, rect)

        pygame.draw.rect(self.surface, self.colors["frame_elements"], rect, 1)

  def render(self):
    self._render_stream_display()

    #self._render_confirmed_signal_list()
    #self._render_confirmed_details()
    #self._render_scan_signal_list()
    #self._render_tx_signal_list()

  def update(self):
    now = time.time()

    #self.pr.enable()

    self.stream_box_data = self.analysis_thread.get_stream_fft_box_data()

    #self.pr.disable()
    #s = io.StringIO()
    #sortby = SortKey.CUMULATIVE
    #ps = pstats.Stats(self.pr, stream=s).sort_stats(sortby)
    #ps.print_stats()
    #print(s.getvalue())

  def process_keydown(self, key):
    if key not in (pygame.K_PAGEUP, pygame.K_PAGEDOWN):
      return

    if key == pygame.K_PAGEUP:
      self.selected_signal -= 1
    elif key == pygame.K_PAGEDOWN:
      self.selected_signal += 1

    self._clamp_selected_emitters()
