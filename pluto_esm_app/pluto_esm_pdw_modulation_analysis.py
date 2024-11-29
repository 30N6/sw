from pluto_esm_hw_pkg import *
import numpy as np

class pluto_esm_pdw_modulation_analysis:
  def __init__(self, config):
    self.sampling_freq      = ADC_CLOCK_FREQUENCY / (ESM_NUM_CHANNELS_NARROW / CHANNELIZER_OVERSAMPLING)
    self.threshold_norm_r   = config["FM_threshold_norm_r"] * self.sampling_freq
    self.threshold_slope    = config["FM_threshold_slope"]
    self.threshold_samples  = config["FM_min_samples"]

  def check_intrapulse_modulation(self, pulse_iq_samples):

