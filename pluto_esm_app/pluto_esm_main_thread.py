import pygame
import pluto_esm_sw_config
import pluto_esm_sequencer
import render_spectrum

class pluto_esm_main_thread:
  SCREEN_SIZE = (1280, 800)
  FPS = 30

  def __init__(self):
    pygame.init()
    self.surface = pygame.display.set_mode(self.SCREEN_SIZE)
    pygame.display.set_caption("pluto_esm")
    self.clock = pygame.time.Clock()

    self.sw_config = pluto_esm_sw_config.pluto_esm_sw_config("./pluto_esm_sample_config.json")
    #self.sequencer = pluto_esm_sequencer.pluto_esm_sequencer(pluto_esm_sw_configdwell_config)

    self.render_spectrum = render_spectrum.render_spectrum(self.surface)

  def run(self):
    running = True
    while (running):
      for i in pygame.event.get():
        if i.type == pygame.QUIT:
          running = False

      #todo: read messages from queue
      #dwell_scheduler.update()


      self.surface.fill((0,0,0))
      self.render_spectrum.render()


      pygame.display.flip()
      self.clock.tick(self.FPS)

    pygame.quit()