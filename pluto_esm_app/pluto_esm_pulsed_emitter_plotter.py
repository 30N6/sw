import numpy as np

class pluto_esm_pulsed_emitter_plotter:

  def __init__(self, plot_dimensions):
    self.plot_dimensions = plot_dimensions

    self.pri_percentile_range = [0.1, 0.90]

  def get_pri_plot(self, sorted_pulse_pri, color):
    i_start   = int(np.round(self.pri_percentile_range[0] * len(sorted_pulse_pri)))
    i_end     = int(np.round(self.pri_percentile_range[1] * len(sorted_pulse_pri)))
    pri_data  = sorted_pulse_pri[i_start:i_end]
    max_pri   = pri_data[-1]

    hist_data = np.zeros(self.plot_dimensions[0])
    hist_scale = (self.plot_dimensions[0] - 1) / max_pri
    pri_scaled = np.round(pri_data * hist_scale).astype(np.uint32)

    for i in range(len(pri_scaled)):
      hist_data[pri_scaled[i]] += 1

    hist_data = np.round((self.plot_dimensions[1] * hist_data) / hist_data.max()).astype(np.uint32)

    hist_image = np.zeros((self.plot_dimensions[0], self.plot_dimensions[1], 3), dtype=np.uint8)
    for i_col in range(self.plot_dimensions[0]):
      if hist_data[i_col] > 0:
        hist_image[i_col, (self.plot_dimensions[1] - hist_data[i_col]):self.plot_dimensions[1] ] = color

    return hist_image, max_pri
