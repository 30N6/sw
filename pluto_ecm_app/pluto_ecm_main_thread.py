import os, sys
import pygame
import pluto_ecm_sw_config
import pluto_ecm_hw_interface
import pluto_ecm_sequencer
import pluto_ecm_analysis_thread
import pluto_ecm_logger
import pluto_ecm_data_recorder
import pluto_ecm_data_loader
import render_status
import render_spectrum
import render_signals

#TODO: find source of numpy warnings
import warnings
warnings.filterwarnings('error', category=RuntimeWarning)

class pluto_ecm_main_thread:
  SCREEN_SIZE = (1280, 800)
  FPS = 60
  VERSION = "v0.01 2025-02-01"

  def __init__(self):
    if len(sys.argv) < 5:
      raise RuntimeError("insufficient number of arguments, expected format: pluto_ecm_app.py [config_file] [log_dir] [local_ip] [pluto_uri]")

    self.config_file  = sys.argv[1]
    self.log_dir      = sys.argv[2]
    self.local_ip     = sys.argv[3]
    self.pluto_uri    = sys.argv[4]

    if not os.path.exists(self.log_dir):
      os.makedirs(self.log_dir)

    self.sw_config = pluto_ecm_sw_config.pluto_ecm_sw_config(self.config_file)

    flags = pygame.SCALED
    if self.sw_config.graphics["fullscreen"]:
      flags |= pygame.FULLSCREEN
    if self.sw_config.graphics["noframe"]:
      flags |= pygame.NOFRAME

    pygame.init()
    self.surface = pygame.display.set_mode(self.SCREEN_SIZE, flags, vsync=1)
    pygame.display.set_caption("pluto_ecm")
    self.clock = pygame.time.Clock()

    if self.sw_config.debug_log:
      log_level = pluto_ecm_logger.pluto_ecm_logger.LL_DEBUG
    else:
      log_level = pluto_ecm_logger.pluto_ecm_logger.LL_INFO

    self.logger       = pluto_ecm_logger.pluto_ecm_logger(self.log_dir, "pluto_ecm_main_thread", log_level)
    self.recorder     = pluto_ecm_data_recorder.pluto_ecm_data_recorder(self.log_dir, "recorded_data", self.sw_config.config["simulation"]["recording_enable"])
    if self.sw_config.sim_enabled:
      self.sim_loader = pluto_ecm_data_loader.pluto_ecm_data_loader(self.logger, self.sw_config.config["simulation"]["playback_filename"], self.sw_config.config["simulation"]["playback_speed"])
    else:
      self.sim_loader = None

    self.hw_interface     = pluto_ecm_hw_interface.pluto_ecm_hw_interface(self.logger, self.pluto_uri, self.local_ip, self.sw_config.config["pluto_dma_reader_path"], self.sw_config.config["pluto_credentials"], self.sw_config.config["simulation"]["playback_enable"])
    self.analysis_thread  = pluto_ecm_analysis_thread.pluto_ecm_analysis_runner(self.logger, self.sw_config)
    self.sequencer        = pluto_ecm_sequencer.pluto_ecm_sequencer(self.logger, self.recorder, self.sw_config,
                                                                    self.hw_interface, self.analysis_thread, self.sim_loader)
    self.render_status    = render_status.render_status(self.surface, self.sw_config, self.hw_interface, self.sequencer, self.analysis_thread, self.VERSION)
    self.render_spectrum  = render_spectrum.render_spectrum(self.surface, self.sw_config, self.sequencer)
    self.render_signals   = render_signals.render_signals(self.surface, self.sw_config, self.analysis_thread, self.sequencer)

  def run(self):
    keydown_handlers  = [self.render_spectrum, self.render_signals]
    keystate_handlers = [self.sequencer]
    update_calls      = [self.hw_interface, self.analysis_thread, self.sequencer, self.render_status, self.render_spectrum, self.render_signals]
    render_calls      = [self.render_status, self.render_spectrum, self.render_signals]

    running = True
    while (running):
      for i in pygame.event.get():
        if i.type == pygame.QUIT:
          running = False
        elif i.type == pygame.KEYDOWN:
          if i.key == pygame.K_ESCAPE:
            running = False

          for handler in keydown_handlers:
            handler.process_keydown(i.key)

      key_state = pygame.key.get_pressed()
      for handler in keystate_handlers:
        handler.process_keystate(key_state)

      self.logger.flush()
      self.recorder.flush()

      for mod in update_calls:
        mod.update()

      self.surface.fill((0,0,0))
      for mod in render_calls:
        mod.render()

      pygame.display.flip()
      self.clock.tick(self.FPS)

    self.shutdown(False)

  def shutdown(self, interrupted):
    #self.hw_interface.shutdown()
    if not interrupted:
      self.analysis_thread.shutdown()

    self.recorder.shutdown("quit")
    self.logger.log(self.logger.LL_INFO, "[main_thread] shutting down")
    pygame.quit()
    self.logger.shutdown("quit")
