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
    self.colors["frame_elements"]       = (0, 255, 192)

    self.font_main                      = pygame.font.SysFont('Consolas', 16)

    self._update_labels()

    self.pr = cProfile.Profile()

  def _update_labels(self):
    self.channel_frequency_label = []
    self.channel_label = []
    for i in range(INTERCEPT_NUM_CHANNELS):
      frequency_str = self.sequencer.get_channel_frequency_str(i)
      self.channel_frequency_label.append(self.font_main.render(frequency_str, True, self.colors["frame_elements"]))
      self.channel_label.append(self.font_main.render("{}".format(i), True, self.colors["frame_elements"]))

    self.trigger_type_label = []
    for i in range(len(self.trigger_type_map)):
      self.trigger_type_label.append(self.font_main.render(self.trigger_type_map[i], True, self.colors["frame_elements"]))

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
          text_data = self.channel_frequency_label[channel_index]
          text_rect = text_data.get_rect()
          text_rect.left = rect_x + 4 #+ self.stream_box_width / 2
          text_rect.centery = rect_y - 8 #+ self.stream_box_height + 12
          self.surface.blit(text_data, text_rect)

          text_data = self.channel_label[channel_index]
          text_rect = text_data.get_rect()
          text_rect.right = rect_x + self.stream_box_width
          text_rect.centery = rect_y - 8
          self.surface.blit(text_data, text_rect)

          text_data = self.trigger_type_label[trigger_type]
          text_rect = text_data.get_rect()
          text_rect.left = rect_x
          text_rect.centery = rect_y + self.stream_box_height + 8
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

  def update(self):
    now = time.time()

    #self.pr.enable()

    #TODO: verify update frequency

    self.stream_box_data = self.analysis_thread.get_stream_fft_box_data()

    #self.pr.disable()
    #s = io.StringIO()
    #sortby = SortKey.CUMULATIVE
    #ps = pstats.Stats(self.pr, stream=s).sort_stats(sortby)
    #ps.print_stats()
    #print(s.getvalue())

  def process_keydown(self, key):
    pass
