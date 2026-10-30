import numpy as np

class pluto_intercept_detail_graphics:
  def __init__(self, config):
    self.config = config

    self.trace_height             = 128
    self.trace_width              = 256
    self.trace_max_dB             = 30
    self.trace_min_dB             = -60
    self.trace_color              = np.asarray([32, 255, 32], dtype=np.uint8)

    self.trace_vertical_px_per_dB = (self.trace_height - 4) / (self.trace_max_dB - self.trace_min_dB)
    self.trace_thickness          = 2

  def get_spectrum_trace(self, fft_power):
    width_scale = fft_power.size // self.trace_width
    power = fft_power.reshape(self.trace_width, width_scale).mean(axis=1)

    power_dB = 10.0 * np.log10(np.maximum(power, 1e-12))
    np.clip(power_dB, self.trace_min_dB, self.trace_max_dB, out=power_dB)

    trace_data = np.zeros((self.trace_width, self.trace_height, 3), dtype=np.uint8)
    trace_x = np.arange(self.trace_width)

    trace_y = self.trace_height - (np.round((power_dB - self.trace_min_dB) * self.trace_vertical_px_per_dB).astype(np.int32) + 2)
    for i in range(self.trace_thickness):
      trace_y_clipped = np.clip(trace_y + i, 0, self.trace_height - 1)
      trace_data[trace_x, trace_y_clipped] = self.trace_color

    return trace_data