import os
import pygame
import pluto_esm_sw_config
import pluto_esm_sequencer
import pluto_esm_hw_interface
import pluto_esm_logger
import render_spectrum

class pluto_esm_main_thread:
  SCREEN_SIZE = (1280, 800)
  FPS = 60
  LOG_DIR = "./log"

  def __init__(self):
    if not os.path.exists(self.LOG_DIR):
      os.makedirs(self.LOG_DIR)

    pygame.init()
    self.surface = pygame.display.set_mode(self.SCREEN_SIZE)
    pygame.display.set_caption("pluto_esm")
    self.clock = pygame.time.Clock()

    self.logger = pluto_esm_logger.pluto_esm_logger(self.LOG_DIR, "pluto_esm_main_thread", pluto_esm_logger.pluto_esm_logger.LL_DEBUG)

    self.sw_config    = pluto_esm_sw_config.pluto_esm_sw_config("./pluto_esm_sample_config.json")
    self.hw_interface = pluto_esm_hw_interface.pluto_esm_hw_interface(self.logger, "ip:192.168.3.100")
    self.sequencer    = pluto_esm_sequencer.pluto_esm_sequencer(self.logger, self.sw_config, self.hw_interface)

    #self.hw_interface.test()
    self.render_spectrum = render_spectrum.render_spectrum(self.surface, self.sw_config, self.sequencer)

  def run(self):
    running = True
    while (running):
      for i in pygame.event.get():
        if i.type == pygame.QUIT:
          running = False

      self.logger.flush()
      #todo: read messages from queue
      #dwell_scheduler.update()
      self.hw_interface.update()
      self.sequencer.update()
      self.render_spectrum.update()

      self.surface.fill((0,0,0))
      self.render_spectrum.render()


      pygame.display.flip()
      self.clock.tick(self.FPS)

    print("sending shutdown")
    self.hw_interface.shutdown()
    pygame.quit()