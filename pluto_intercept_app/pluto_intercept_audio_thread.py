import pluto_intercept_logger
import time
import multiprocessing
from multiprocessing import Process, Queue, Manager
import traceback
import copy
import signal
from collections import deque
import numpy as np
import scipy as sp
import pygame

import tracemalloc
import cProfile, pstats, io
from pstats import SortKey

class pluto_intercept_audio_thread:

  def __init__(self, arg):
    self.input_queue      = arg["input_queue"]
    self.logger           = pluto_intercept_logger.pluto_intercept_logger(arg["log_dir"], "pluto_intercept_audio_thread", arg["log_level"])

    self.input_buffer           = np.empty(0, dtype=np.float32)
    self.audio_chunks           = deque()
    self.audio_active           = False
    self.audio_chunks_to_buffer = 4

    self.pr = cProfile.Profile()

    pygame.mixer.init(frequency=16000, size=-16, channels=1, buffer=2048)

    self.logger.log(self.logger.LL_INFO, "init: queue={}, current_process={}".format(self.input_queue, multiprocessing.current_process()))

    #tracemalloc.start()

  def _process_data(self, report):
    assert (report["fs"] == 40e3) # x2/5 -> 16 khz audio

    if report["features"]["modulation"] == "AM":
      selected_data = report["details"]["iq_amplitude"]
      #print("{} : playing AM: {}".format(time.time(), selected_data.size))
    else:
      selected_data = report["details"]["iq_frequency"]
      #print("{} : playing FM: {}".format(time.time(), selected_data.size))

    self.input_buffer = np.concatenate((self.input_buffer, selected_data))

    n = (self.input_buffer.size // 5) * 5
    if n == 0:
        return
    audio_block = self.input_buffer[:n]
    self.input_buffer = self.input_buffer[n:] # keep the remainder (< 5 samples)

    audio_data_f = sp.signal.resample_poly(audio_block, up=2, down=5)
    audio_data_i = np.clip(audio_data_f * 32767, -32768, 32767).astype(np.int16)
    audio_data_s = np.column_stack((audio_data_i, audio_data_i))
    self.audio_chunks.append(audio_data_s)

    if len(self.audio_chunks) > self.audio_chunks_to_buffer:
      self.audio_active = True

  def run(self):
    running = True
    mixer_channel = pygame.mixer.Channel(0)

    try:
      while running:
        #self.pr.enable()
        #start = time.time()

        #read off data from the queue before calling update() - helps ensure a clean shutdown
        while not self.input_queue.empty():
          #self.logger.log(self.logger.LL_INFO, "input_queue.get()")
          data = self.input_queue.get()

          if isinstance(data, dict):
            #self.logger.log(self.logger.LL_INFO, "input_queue: got dict: time_diff={:.3f}".format(time.time() - data["timestamp"]))
            self._process_data(data)
          else:
            if data == "CMD_STOP":
              self.logger.log(self.logger.LL_INFO, "CMD_STOP")
              self.logger.flush()
              running = False
            else:
              raise RuntimeError("invalid command")
              running = False

        if self.audio_active and (len(self.audio_chunks) > 0) and (mixer_channel.get_queue() is None):
          next_chunk = self.audio_chunks.popleft()
          sound = pygame.sndarray.make_sound(next_chunk)
          mixer_channel.queue(sound)

          if len(self.audio_chunks) == 0:
            self.audio_active = False

        else:
          time.sleep(0.001)

        #print("audio_thread: {:.3f}".format(time.time() - start))
        #self.pr.disable()
        #s = io.StringIO()
        #sortby = SortKey.CUMULATIVE
        #ps = pstats.Stats(self.pr, stream=s).sort_stats(sortby)
        #ps.print_stats()
        #print(s.getvalue())

      self.shutdown("graceful exit")
    except Exception as e:
      self.logger.log(self.logger.LL_INFO, "Exception: {}".format(e))
      self.logger.log(self.logger.LL_INFO, "Traceback: {}".format(traceback.format_exc()))
      self.logger.flush()
      self.shutdown("exception")

  def shutdown(self, reason):
    pygame.mixer.quit()
    self.logger.shutdown(reason)

audio_thread = 0

def pluto_intercept_audio_thread_func(arg):
  global audio_thread

  audio_thread = pluto_intercept_audio_thread(arg)

  signal.signal(signal.SIGTERM, pluto_intercept_audio_thread_sig_handler)

  try:
    audio_thread.run()
  except KeyboardInterrupt:
    audio_thread.shutdown("interrupted")
  except Exception as e:
    audio_thread.shutdown("exception: {}".format(e))

  print("pluto_intercept_audio_thread_func: done")

def pluto_intercept_audio_thread_sig_handler(arg1, arg2):
  global audio_thread
  audio_thread.shutdown("sig handler: {} {}".format(arg1, arg2))

class pluto_intercept_audio_runner:
  def __init__(self, logger, sw_config):
    self.logger       = logger
    self.mp_manager   = Manager()
    self.input_queue  = self.mp_manager.Queue()
    self.running      = True

    self.process = Process(target=pluto_intercept_audio_thread_func,
                           args=({"input_queue": self.input_queue, "log_dir": logger.path, "log_level": logger.min_level, "sw_config": sw_config}, ))
    self.process.start()

  def submit_data(self, report):
    if self.running:
      self.input_queue.put(report, block=False)
    else:
      self.logger.log(self.logger.LL_INFO, "[audio] submit_data: shutting down -- report dropped, seq={}".format(report["global_seq_num"]))

  def shutdown(self):
    self.running = False
    self.logger.log(self.logger.LL_INFO, "[audio] shutdown")
    if self.process.is_alive():
      for i in range(100):
        self.logger.log(self.logger.LL_INFO, "[audio] sending CMD_STOP to audio thread")
        self.input_queue.put("CMD_STOP", block=False)
        self.process.join(1.0)
        self.logger.log(self.logger.LL_INFO, "[audio] shutdown: process.exitcode={} is_alive={}".format(self.process.exitcode, self.process.is_alive()))
        if not self.process.is_alive():
          break
    else:
      self.logger.log(self.logger.LL_INFO, "[audio] shutdown: process already dead, exitcode={}".format(self.process.exitcode))

    self.logger.flush()

    while not self.input_queue.empty():
      data = self.input_queue.get(block=False)
      self.logger.log(self.logger.LL_INFO, "[audio] shutdown: input_queue data dropped")
