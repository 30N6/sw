import pygame

class render_spectrum:

  def __init__(self, surface):
    self.surface = surface

  def render(self):
    pygame.draw.rect(self.surface, (0, 0, 255), [0, 0, 640, 768], 1)

    pygame.draw.rect(self.surface, (0, 128, 128), [16, 16,  608, 64], 1)
    pygame.draw.rect(self.surface, (0, 128, 128), [16, 128, 608, 360], 1)
    pygame.draw.rect(self.surface, (0, 128, 128), [16, 512, 608, 232], 1)

  def process_dwell_updates(self):
    pass