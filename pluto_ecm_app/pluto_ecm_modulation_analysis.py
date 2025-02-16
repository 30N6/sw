from pluto_ecm_hw_pkg import *
import numpy as np
import scipy as sp
import time
import traceback

class pluto_ecm_modulation_analysis:
  def __init__(self, config):
    self.fs = ADC_CLOCK_FREQUENCY / (ECM_NUM_CHANNELS / CHANNELIZER_OVERSAMPLING)
    self.dt = 1/self.fs

    self.lora_num_chunks        = config["analysis_config"]["modulation_analysis"]["elrs-lora"]["parameters"]["lora_num_chunks"]
    self.lora_peak_threshold    = config["analysis_config"]["modulation_analysis"]["elrs-lora"]["parameters"]["lora_peak_threshold"]
    self.cvbs_xcorr_window_inc  = config["analysis_config"]["modulation_analysis"]["cvbs"]["parameters"]["cvbs_xcorr_window_inc"]
    self.cvbs_xcorr_window_exc  = config["analysis_config"]["modulation_analysis"]["cvbs"]["parameters"]["cvbs_xcorr_window_exc"]

    self.cvbs_xcorr_window_inc_by_len = {}
    self.cvbs_xcorr_window_exc_by_len = {}
    for i in range(9, 12):
      data_len = 2**i
      self.cvbs_xcorr_window_inc_by_len[data_len] = [int(self.cvbs_xcorr_window_inc[0] // self.dt), int(self.cvbs_xcorr_window_inc[1] // self.dt)]
      self.cvbs_xcorr_window_exc_by_len[data_len] = [int(self.cvbs_xcorr_window_exc[0] // self.dt), int(self.cvbs_xcorr_window_exc[1] // self.dt)]

  def process_iq_data(self, report):
    t_start = time.time()
    try:
      iq_data = report["iq_data"]
      timestamp = report["sw_timestamp"]

      padded_length = 2**int(np.ceil(np.log2(iq_data.size)))
      samples_to_pad = padded_length - iq_data.size
      iq_data_padded = np.pad(iq_data, (0, samples_to_pad))

      phase_wrapped     = np.arctan2(np.imag(iq_data), np.real(iq_data))  #TODO: I/Q ordering
      phase_unwrapped   = np.unwrap(phase_wrapped)
      iq_freq           = (1/(2*np.pi)) * np.diff(phase_unwrapped) / self.dt
      iq_freq_mean      = np.mean(iq_freq)
      iq_padded_fft     = np.abs(np.fft.fftshift(np.fft.fft(iq_data_padded)))
      iq_padded_fft_abs = np.abs(iq_padded_fft)
      iq_power          = np.square(np.real(iq_data)) + np.square(np.imag(iq_data))

      r = report.copy()
      r.pop("iq_data")
      r.pop("iq_length")

      analysis = {}
      analysis["power_mean"] = float(np.mean(iq_power))
      analysis["power_max"] = float(np.max(iq_power))
      analysis["fft_mean"], analysis["fft_std"] = self._get_fft_stats(iq_padded_fft_abs)
      analysis["bfsk_r_squared"], analysis["bfsk_freq_spread"], analysis["bfsk_len_peak"] = self._analyze_bfsk(iq_freq)
      analysis["lora_r_squared"], analysis["lora_slope"], analysis["lora_peak_count_ratio"], analysis["lora_peak_spacing_ratio"] = self._analyze_lora(iq_data, iq_freq, iq_padded_fft_abs)
      analysis["lfm_r_squared"], analysis["lfm_slope"] = self._analyze_lfm(iq_freq, iq_freq_mean)
      analysis["cvbs_xcorr_1"], analysis["cvbs_xcorr_2"] = self._analyze_cvbs(iq_padded_fft)
      analysis["iq_length"] = report["iq_length"]

      r["analysis"] = analysis

      t_end = time.time()
      r["processing_time"] = t_end - t_start
      r["time_since_read"] = t_end - timestamp
      r["iq_data"] = [[float(np.real(report["iq_data"][i])), float(np.imag(report["iq_data"][i]))] for i in range(report["iq_data"].size)]

      #if (analysis["lora_r_squared"] > 0.7):
      #  print("LORA: [{}] {:.3f} {:.1f} {:.2f} {:.2f} -- {:.6f} {:.6f}".format(r["hw_timestamp"], analysis["lora_r_squared"], analysis["lora_slope"] / (1e3/1e-6), analysis["lora_peak_count_ratio"], analysis["lora_peak_spacing_ratio"], t_end - t_start, t_end - timestamp))
      #if (analysis["lfm_r_squared"] > 0.7):
      #  print("LFM: [{}] {:.3f} {:.1f}".format(r["hw_timestamp"], analysis["lfm_r_squared"], analysis["lfm_slope"] / (1e3/1e-6)))
      return r

    except Exception:
      s = traceback.format_exc()
      print(s)
      return {"exception": s}

    #print("FSK: {:.3f} {:.1f}".format(fsk_r_squared, fsk_freq_spread))
    #print("FSK: {} {}".format(fsk_r_squared, fsk_freq_spread))

  def _get_fft_stats(self, iq_padded_fft_abs):
    f = np.arange(-iq_padded_fft_abs.size/2, iq_padded_fft_abs.size/2) * self.fs / iq_padded_fft_abs.size

    fft_sum       = np.sum(iq_padded_fft_abs)
    fft_scaled    = iq_padded_fft_abs * (1/fft_sum)
    fft_weighted  = fft_scaled * f

    fft_mean      = np.sum(fft_weighted)
    fft_var       = np.sum(fft_scaled * np.square(f - fft_mean))

    return fft_mean, np.sqrt(fft_var)

  def _analyze_lora(self, iq_data, iq_freq, iq_padded_fft_abs):
    r_squared, mean_slope = self._get_best_lora_poly_fit(iq_freq)
    peak_count_ratio, peak_spacing_ratio = self._get_lora_fit_metrics(iq_data, iq_padded_fft_abs, mean_slope)
    return r_squared, mean_slope, peak_count_ratio, peak_spacing_ratio

  def _get_lora_fit_metrics(self, iq_data, iq_padded_fft_abs, original_slope):
    t_chirp = np.arange(iq_data.size) * self.dt
    f_chirp = -0.5 * original_slope * t_chirp
    y_chirp = np.exp(2j * np.pi * f_chirp * t_chirp)

    iq_dechirped = iq_data * y_chirp
    iq_dechirped = np.pad(iq_dechirped, (0, iq_padded_fft_abs.size - iq_dechirped.size))

    iq_dechirped_fft = np.abs(np.fft.fftshift(np.fft.fft(iq_dechirped)))

    loc_a, props = sp.signal.find_peaks(iq_padded_fft_abs, height=(self.lora_peak_threshold * np.max(iq_padded_fft_abs)))
    loc_b, props = sp.signal.find_peaks(iq_dechirped_fft, height=(self.lora_peak_threshold * np.max(iq_dechirped_fft)))

    if loc_a.size < 2:
      return 0, 0

    if loc_b.size > 0:
      peak_count_ratio = loc_a.size / loc_b.size
    else:
      peak_count_ratio = 0

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

      if len(p_freq) < 2:
        print("_try_lora_poly_fit: polynomial fit failed -- p_freq={} p_info={}".format(p_freq, p_info))
        return 0, 0

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

  def _get_bfsk_fit_metrics(self, iq_freq, iq_freq_mean):
    #y_cluster = np.zeros(iq_freq.size, np.uint32)
    y_cluster       = iq_freq >= iq_freq_mean
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

    for i in range(2):
      y_k             = iq_freq[y_cluster == i]
      mu_cluster[i]   = np.mean(y_k)
      ss_residual[i]  = np.sum(np.square(y_k - mu_cluster[i]))

    ss_total    = np.sum(np.square(iq_freq - iq_freq_mean))
    r_squared   = 1 - np.sum(ss_residual) / ss_total
    freq_spread = np.abs(np.max(mu_cluster) - np.min(mu_cluster))

    det_len_peak = np.argmax(det_len_hist)

    return r_squared, freq_spread, det_len_peak

  def _analyze_bfsk(self, iq_freq):
    r_squared = np.zeros(2)
    freq_spread = np.zeros(2)
    det_len_peak = np.zeros(2)

    input_iq_freq       = [iq_freq[0:iq_freq.size//2], iq_freq[iq_freq.size//2:-1]]
    input_iq_freq_mean  = [np.mean(input_iq_freq[0]), np.mean(input_iq_freq[1])]

    for i in range(2):
      r_squared[i], freq_spread[i], det_len_peak[i] = self._get_bfsk_fit_metrics(input_iq_freq[i], input_iq_freq_mean[i])

    max_i = np.argmax(r_squared)
    return r_squared[max_i], freq_spread[max_i], det_len_peak[max_i]

  def _analyze_lfm(self, iq_freq, iq_freq_mean):
    freq_x = np.arange(iq_freq.size) * self.dt

    [p_freq, p_info]  = np.polynomial.polynomial.Polynomial.fit(freq_x, iq_freq, deg=1, full=True)
    p_freq            = p_freq.convert().coef

    mean_slope        = p_freq[1]
    ss_residual       = p_info[0][0]
    ss_total          = np.sum((iq_freq - iq_freq_mean)**2)
    r_squared         = 1 - ss_residual/ss_total

    return r_squared, mean_slope

  def _analyze_cvbs(self, iq_padded_fft):
    if iq_padded_fft.size not in self.cvbs_xcorr_window_inc_by_len:
      return 0, 0

    w_inc = self.cvbs_xcorr_window_inc_by_len[iq_padded_fft.size]
    w_exc = self.cvbs_xcorr_window_exc_by_len[iq_padded_fft.size]

    fft_conj = np.conjugate(iq_padded_fft)
    fft_prod = iq_padded_fft * fft_conj
    xcorr = np.abs(np.fft.ifft(fft_prod))

    v_inc = xcorr[w_inc[0] : w_inc[1]]
    v_exc = np.concatenate((xcorr[w_exc[0] : w_inc[0]], xcorr[w_inc[1] : w_exc[1]]))

    inc_max = np.max(v_inc)
    cvbs_xcorr_1 = float(inc_max / xcorr[0])
    cvbs_xcorr_2 = float(min(np.mean(v_exc) / inc_max, 1))

    return cvbs_xcorr_1, cvbs_xcorr_2
