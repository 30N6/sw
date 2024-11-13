import os
import pygame
import pluto_esm_sw_config
import pluto_esm_sequencer
import pluto_esm_hw_interface
import pluto_esm_logger
import pluto_esm_data_recorder
import pluto_esm_data_loader
import render_spectrum
import render_status

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

    self.sw_config    = pluto_esm_sw_config.pluto_esm_sw_config("./pluto_esm_sample_config_2.json")
    self.logger       = pluto_esm_logger.pluto_esm_logger(self.LOG_DIR, "pluto_esm_main_thread", pluto_esm_logger.pluto_esm_logger.LL_DEBUG)

    self.recorder     = pluto_esm_data_recorder.pluto_esm_data_recorder(self.LOG_DIR, "recorded_data", self.sw_config.enable_recording)
    if self.sw_config.sim_enabled:
      self.sim_loader = pluto_esm_data_loader.pluto_esm_data_loader(self.logger, self.sw_config.sim_filename)
    else:
      self.sim_loader = None

    self.hw_interface = pluto_esm_hw_interface.pluto_esm_hw_interface(self.logger, "ip:192.168.3.100")
    self.sequencer    = pluto_esm_sequencer.pluto_esm_sequencer(self.logger, self.recorder, self.sw_config, self.hw_interface, self.sim_loader)

    #self.hw_interface.test()
    self.render_status    = render_status.render_status(self.surface, self.sw_config, self.sequencer)
    self.render_spectrum  = render_spectrum.render_spectrum(self.surface, self.sw_config, self.sequencer)

  def run(self):
    running = True
    while (running):
      for i in pygame.event.get():
        if i.type == pygame.QUIT:
          running = False

      self.logger.flush()
      self.recorder.flush()

      self.hw_interface.update()
      self.sequencer.update()
      self.render_status.update()
      self.render_spectrum.update()
      #TODO: replace with loop

      self.surface.fill((0,0,0))
      self.render_status.render()
      self.render_spectrum.render()

      pygame.display.flip()
      self.clock.tick(self.FPS)

    print("sending shutdown")
    self.hw_interface.shutdown()
    self.logger.shutdown("quit")
    self.recorder.shutdown("quit")
    pygame.quit()