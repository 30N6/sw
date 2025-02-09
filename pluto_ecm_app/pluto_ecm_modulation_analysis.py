from pluto_ecm_hw_pkg import *
import numpy as np
import scipy as sp
import time

class pluto_ecm_modulation_analysis:
  def __init__(self, config):
    self.fs = ADC_CLOCK_FREQUENCY / (ECM_NUM_CHANNELS / CHANNELIZER_OVERSAMPLING)
    self.dt = 1/self.fs

    self.lora_num_chunks      = [4, 16] #TODO: config
    self.lora_peak_threshold  = 0.25 #TODO: config

  def process_iq_data(self, iq_data):
    t_start = time.time()
    try:

      padded_length = 2**int(np.ceil(np.log2(iq_data.size)))
      samples_to_pad = padded_length - iq_data.size
      iq_data_padded = np.pad(iq_data, (0, samples_to_pad))

      phase_wrapped   = np.arctan2(np.imag(iq_data), np.real(iq_data))  #TODO: I/Q ordering
      phase_unwrapped = np.unwrap(phase_wrapped)
      iq_freq         = (1/(2*np.pi)) * np.diff(phase_unwrapped) / self.dt

      iq_padded_fft   = np.abs(np.fft.fftshift(np.fft.fft(iq_data_padded)))

      fsk_r_squared, fsk_freq_spread = self._analyze_bfsk(iq_freq)
      lora_r_squared, lora_mean_slope, lora_peak_count_ratio, lora_peak_spacing_ratio = self._analyze_lora(iq_data, iq_freq, iq_padded_fft)

      t_end = time.time()
      if (lora_r_squared > 0.7):
        print("LORA: {:.3f} {:.1f} {:.2f} {:.2f} -- {:.6f}".format(lora_r_squared, lora_mean_slope / (1e3/1e-6), lora_peak_count_ratio, lora_peak_spacing_ratio, t_end - t_start))

    except Exception as e:
      print(e)

    #print("FSK: {:.3f} {:.1f}".format(fsk_r_squared, fsk_freq_spread))
    #print("FSK: {} {}".format(fsk_r_squared, fsk_freq_spread))

  def _analyze_lora(self, iq_data, iq_freq, iq_padded_fft):
    r_squared, mean_slope = self._get_best_lora_poly_fit(iq_freq)
    peak_count_ratio, peak_spacing_ratio = self._get_lora_fit_metrics(iq_data, iq_padded_fft, mean_slope)
    return r_squared, mean_slope, peak_count_ratio, peak_spacing_ratio

  def _get_lora_fit_metrics(self, iq_data, iq_padded_fft, original_slope):
    t_chirp = np.arange(iq_data.size) * self.dt
    f_chirp = -0.5 * original_slope * t_chirp
    y_chirp = np.exp(2j * np.pi * f_chirp * t_chirp)

    iq_dechirped = iq_data * y_chirp
    iq_dechirped = np.pad(iq_dechirped, (0, iq_padded_fft.size - iq_dechirped.size))

    iq_dechirped_fft = np.abs(np.fft.fftshift(np.fft.fft(iq_dechirped)))

    loc_a, props = sp.signal.find_peaks(iq_padded_fft, height=(self.lora_peak_threshold * np.max(iq_padded_fft)))
    loc_b, props = sp.signal.find_peaks(iq_dechirped_fft, height=(self.lora_peak_threshold * np.max(iq_dechirped_fft)))

    peak_count_ratio = loc_a.size / loc_b.size

    if loc_b.size > 1:
      peak_spacing_ratio = np.mean(np.diff(loc_a)) / np.mean(np.diff(loc_b))
    else:
      peak_spacing_ratio = 0

    return peak_count_ratio, peak_spacing_ratio

  def _try_lora_poly_fit(self, iq_freq, num_chunks):
    chunk_length = iq_freq.size // num_chunks

    r_squared   = np.zeros(num_chunks)
    mean_slope  = np.zeros(num_chunks)

    chunk_x = np.arange(chunk_length) * self.dt

    for i in range(num_chunks):
      chunk_y = iq_freq[i*chunk_length : (i+1)*chunk_length]

      [p_freq, p_info]  = np.polynomial.polynomial.Polynomial.fit(chunk_x, chunk_y, deg=1, full=True)
      p_freq            = p_freq.convert().coef

      mean_slope[i]     = p_freq[1]
      ss_residual       = p_info[0][0]
      ss_total          = np.sum((chunk_y - np.mean(chunk_y))**2)
      r_squared[i]      = 1 - ss_residual/ss_total

    return mean_slope, r_squared

  def _get_best_lora_poly_fit(self, iq_freq):
    mean_slope  = np.zeros(0)
    r_squared   = np.zeros(0)

    for num_chunks in self.lora_num_chunks:
      [ms, rs] = self._try_lora_poly_fit(iq_freq, num_chunks)
      mean_slope = np.append(mean_slope, ms)
      r_squared  = np.append(r_squared, rs)

    max_i = np.argmax(r_squared)
    return r_squared[max_i], mean_slope[max_i]

  def _analyze_bfsk(self, iq_freq):
    M = 2

    y_mean = np.mean(iq_freq, 0)

    #y_cluster = np.zeros(iq_freq.size, np.uint32)
    y_cluster       = iq_freq >= y_mean
    y_cluster_diff  = np.diff(y_cluster)

    ss_residual   = np.zeros(2)
    mu_cluster    = np.zeros(2)
    det_len_hist  = np.zeros(iq_freq.size)
    det_len       = 1

    for i in range(iq_freq.size-1):
      if y_cluster_diff[i]:
        det_len_hist[det_len] += 1
        det_len = 1
      else:
        det_len += 1

    for i in range(M):
      y_k             = iq_freq[y_cluster == i]
      mu_cluster[i]   = np.mean(y_k)
      ss_residual[i]  = np.sum(np.square(y_k - mu_cluster[i]))

    ss_total    = np.sum(np.square(iq_freq - y_mean))
    r_squared   = 1 - np.sum(ss_residual) / ss_total
    freq_spread = np.abs(np.max(mu_cluster) - np.min(mu_cluster))

    return r_squared, freq_spread

  def check_intrapulse_modulation(self, pulse_duration, pulse_iq_samples):
    valid_duration = min(ESM_PDW_BUFFERED_SAMPLES_PER_FRAME, pulse_duration)
    if (valid_duration - ESM_PDW_BUFFERED_IQ_DELAY_SAMPLES) < self.threshold_samples:
      return None

    pulse_iq = np.asarray(pulse_iq_samples[ESM_PDW_BUFFERED_IQ_DELAY_SAMPLES:valid_duration])

    phase_wrapped   = np.arctan2(pulse_iq[:, 0], pulse_iq[:, 1])
    phase_unwrapped = np.unwrap(phase_wrapped)

    y_freq = (1/(2*np.pi)) * np.diff(phase_unwrapped) / self.dt
    x_freq = np.arange(0, y_freq.size * self.dt, self.dt)

    [p_freq, p_info] = np.polynomial.polynomial.Polynomial.fit(x_freq, y_freq, deg=1, full=True)

    p_freq = p_freq.convert().coef
    y_poly = np.polynomial.polynomial.polyval(x_freq, p_freq)

    if len(p_freq) < 2:
      print("check_intrapulse_modulation: polynomial fit failed -- p_freq={} p_info={} x_freq={} y_freq={}".format(p_freq, p_info, x_freq, y_freq))
      return None

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
