import pygame
import time
import numpy as np

class render_status:
  def __init__(self, surface, sw_config, sequencer):
    self.surface    = surface
    self.sequencer  = sequencer

    self.font = pygame.font.SysFont('Consolas', 14)

    self.frame_times = np.zeros(50)

  def render(self):
    self.frame_times = np.roll(self.frame_times, 1)
    self.frame_times[0] = time.time()
    time_diff = -np.diff(self.frame_times)
    mean_time_diff = np.mean(time_diff)
    max_time_diff = np.max(time_diff)

    state_str = "{:>20} {:>16} {:>4.1f}/{:>4.1f} fps".format(self.sequencer.state, self.sequencer.dwell_state, 1.0/mean_time_diff, 1.0/max_time_diff)
    text_data = self.font.render(state_str, True, (0, 192, 192))
    text_rect = text_data.get_rect()
    text_rect.left = 16
    text_rect.bottom = 792
    self.surface.blit(text_data, text_rect)

  def update(self):
    pass
