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

    self.colors["cal_old"] = (192, 0, 0)
    self.colors["cal_new"] = (0, 192, 0)
    self.colors["dwell_old"] = (64, 0, 0)
    self.colors["dwell_new"] = (0, 255, 0)
    self.colors["frame_elements"] = (0, 128, 128)
    self.colors["grid_lines"] = (0, 128, 128)
    self.colors["zoom_marker"] = (0, 192, 192)

    self.font = pygame.font.SysFont('Consolas', 12)

  def render(self):

    pygame.draw.rect(self.surface, self.colors["border"], [640, 0,   384, 384], 1)
    pygame.draw.rect(self.surface, self.colors["border"], [640, 384, 384, 384], 1)

  def update(self):
    #self.pr.enable()
    pass
