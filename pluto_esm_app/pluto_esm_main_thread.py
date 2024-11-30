import os
import pygame
import pluto_esm_sw_config
import pluto_esm_sequencer
import pluto_esm_hw_interface
import pluto_esm_analysis_thread
import pluto_esm_logger
import pluto_esm_data_recorder
import pluto_esm_data_loader
import render_status
import render_spectrum
import render_emitters

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

    self.sw_config    = pluto_esm_sw_config.pluto_esm_sw_config("./pluto_esm_sample_config.json")
    self.logger       = pluto_esm_logger.pluto_esm_logger(self.LOG_DIR, "pluto_esm_main_thread", pluto_esm_logger.pluto_esm_logger.LL_INFO)

    self.recorder     = pluto_esm_data_recorder.pluto_esm_data_recorder(self.LOG_DIR, "recorded_data", self.sw_config.enable_recording)
    if self.sw_config.sim_enabled:
      self.sim_loader = pluto_esm_data_loader.pluto_esm_data_loader(self.logger, self.sw_config.sim_filename)
    else:
      self.sim_loader = None

    self.hw_interface     = pluto_esm_hw_interface.pluto_esm_hw_interface(self.logger, "ip:192.168.3.100", "192.168.3.10")
    self.analysis_thread  = pluto_esm_analysis_thread.pluto_esm_analysis_runner(self.logger, self.sw_config)
    self.sequencer        = pluto_esm_sequencer.pluto_esm_sequencer(self.logger, self.recorder, self.sw_config,
                                                                    self.hw_interface, self.analysis_thread, self.sim_loader)

    #self.hw_interface.test()
    self.render_status    = render_status.render_status(self.surface, self.sw_config, self.sequencer)
    self.render_spectrum  = render_spectrum.render_spectrum(self.surface, self.sw_config, self.sequencer)
    self.render_emitters  = render_emitters.render_emitters(self.surface, self.sw_config, self.analysis_thread)

  def run(self):
    key_handlers = [self.render_spectrum]
    update_calls = [self.hw_interface, self.analysis_thread, self.sequencer, self.render_status, self.render_spectrum, self.render_emitters]
    render_calls = [self.render_status, self.render_spectrum, self.render_emitters]

    running = True
    while (running):
      for i in pygame.event.get():
        if i.type == pygame.QUIT:
          running = False
        elif i.type == pygame.KEYDOWN:
          for handler in key_handlers:
            handler.process_keydown(i.key)

      self.logger.flush()
      self.recorder.flush()

      for mod in update_calls:
        mod.update()

      self.surface.fill((0,0,0))
      for mod in render_calls:
        mod.render()

      pygame.display.flip()
      self.clock.tick(self.FPS)

    self.shutdown()
    os._exit(0)

  def shutdown(self):
    self.hw_interface.shutdown()
    self.analysis_thread.shutdown()
    self.recorder.shutdown("quit")
    self.logger.log(self.logger.LL_INFO, "[main_thread] shutting down")
    pygame.quit()
    self.logger.shutdown("quit")
