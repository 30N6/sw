from pluto_esm_hw_pkg import *
import numpy as np

class pluto_esm_pdw_modulation_analysis:
  def __init__(self, config):
    self.sampling_freq        = ADC_CLOCK_FREQUENCY / (ESM_NUM_CHANNELS_NARROW / CHANNELIZER_OVERSAMPLING)
    self.dt                   = 1/self.sampling_freq
    self.threshold_residual   = config["FM_threshold_residual"] * self.sampling_freq
    self.threshold_r_squared  = config["FM_threshold_r_squared"]
    self.threshold_slope      = config["FM_threshold_slope"]
    self.threshold_samples    = config["FM_min_samples"]


  def check_intrapulse_modulation(self, pulse_duration, pulse_iq_samples):
    valid_duration = min(ESM_PDW_BUFFERED_SAMPLES_PER_FRAME, pulse_duration)
    if (valid_duration - ESM_PDW_BUFFERED_IQ_DELAY_SAMPLES) < self.threshold_samples:
      return None

    pulse_iq = np.asarray(pulse_iq_samples[ESM_PDW_BUFFERED_IQ_DELAY_SAMPLES:valid_duration])

    phase_wrapped   = np.arctan2(pulse_iq[:, 1], pulse_iq[:, 0])
    phase_unwrapped = np.unwrap(phase_wrapped)

    y_freq = (1/(2*np.pi)) * np.diff(phase_unwrapped) / self.dt
    x_freq = np.arange(0, y_freq.size * self.dt, self.dt)

    [p_freq, p_info] = np.polynomial.polynomial.Polynomial.fit(x_freq, y_freq, deg=1, full=True)
    p_freq = p_freq.convert().coef

    y_poly = np.polynomial.polynomial.polyval(x_freq, p_freq)

    freq_initial  = p_freq[0]
    freq_slope    = p_freq[1] * 1e-6

    ss_residual   = p_info[0][0]
    ss_total      = np.sum((y_freq - np.mean(y_freq))**2)
    r_squared     = 1 - ss_residual/ss_total
    mean_residual = np.mean(np.abs(y_freq - y_poly))

    matched_residual  = (mean_residual < self.threshold_residual)
    matched_r_squared = (r_squared > self.threshold_r_squared)
    matched_slope     = (abs(freq_slope) > self.threshold_slope)

    #print("mod_analysis: duration={} matched_res={} matched_r2={} matched_slope={}".format(valid_duration, matched_residual, matched_r_squared, matched_slope))
    #print("mod_analysis:   mean_residual={}  r_squared={}  slope={}".format(mean_residual, r_squared, freq_slope))

    if matched_residual and matched_r_squared and matched_slope:
      mod_type = "FM"
    else:
      mod_type = None

    return {"modulation_type": mod_type, "LFM_slope": freq_slope, "LFM_r_squared": r_squared, "LFM_mean_residual": mean_residual}
