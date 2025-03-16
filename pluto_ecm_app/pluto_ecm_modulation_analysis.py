from pluto_ecm_hw_pkg import *
import numpy as np
import scipy as sp
import time
import traceback

class pluto_ecm_modulation_analysis:
  def __init__(self, config):
    self.fs = ADC_CLOCK_FREQUENCY / (ECM_NUM_CHANNELS / CHANNELIZER_OVERSAMPLING)
    self.dt = 1/self.fs

    self.stft_length = 16

    self.lora_num_chunks              = config["analysis_config"]["modulation_analysis"]["elrs-lora"]["parameters"]["lora_num_chunks"]
    self.lora_peak_threshold          = config["analysis_config"]["modulation_analysis"]["elrs-lora"]["parameters"]["lora_peak_threshold"]
    self.cvbs_xcorr_window_inc        = config["analysis_config"]["modulation_analysis"]["cvbs"]["parameters"]["cvbs_xcorr_window_inc"]
    self.cvbs_xcorr_window_exc        = config["analysis_config"]["modulation_analysis"]["cvbs"]["parameters"]["cvbs_xcorr_window_exc"]
    #self.dji_ocusync4_fsk_short_len = config["analysis_config"]["modulation_analysis"]["dji-ocusync-4"]["parameters"]["fsk_short_len"]  #TODO: remove
    self.ble_trunc_front_samples      = config["analysis_config"]["modulation_analysis"]["ble-bfsk-trunc"]["parameters"]["bfsk_trunc_front_samples"]
    self.ble_trunc_rear_power_thresh  = 10**(config["analysis_config"]["modulation_analysis"]["ble-bfsk-trunc"]["parameters"]["bfsk_trunc_rear_power_dB"]/10)
    self.ofdm_min_acorr_peak_count    = config["analysis_config"]["modulation_analysis"]["ofdm-generic"]["parameters"]["ofdm_min_acorr_peak_count"]

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
      iq_stft           = self._get_stft(iq_data)

      iq_padded_fft_conj  = np.conjugate(iq_padded_fft)
      iq_padded_fft_prod  = iq_padded_fft * iq_padded_fft_conj
      iq_acorr_abs        = np.abs(np.fft.ifft(iq_padded_fft_prod))

      r = report.copy()
      r.pop("iq_data")
      r.pop("iq_length")

      analysis = {}
      analysis["power_mean"] = float(np.mean(iq_power))
      analysis["power_max"] = float(np.max(iq_power))
      analysis["fft_mean"], analysis["fft_std"] = self._get_fft_stats(iq_padded_fft_abs)

      analysis["bfsk_r_squared"], analysis["bfsk_freq_spread"], analysis["bfsk_len_peak"] = self._analyze_bfsk(iq_freq)
      analysis["bfsk_trunc_r_squared"], analysis["bfsk_trunc_freq_spread"], analysis["bfsk_trunc_len_peak"] = self._analyze_bfsk_trunc(iq_freq, iq_power, self.ble_trunc_front_samples, self.ble_trunc_rear_power_thresh)

      #analysis["bfsk_short_r_squared"], analysis["bfsk_short_freq_spread"] = self._analyze_fsk_short(iq_freq, 2, self.dji_ocusync4_fsk_short_len) #TODO: remove
      #analysis["tfsk_short_r_squared"], analysis["tfsk_short_freq_spread"] = self._analyze_fsk_short(iq_freq, 3, self.dji_ocusync4_fsk_short_len) #TODO: remove
      #analysis["tfsk_bfsk_short_r_squared_ratio"] = analysis["tfsk_short_r_squared"] / analysis["bfsk_short_r_squared"] #TODO: remove

      analysis["lora_r_squared"], analysis["lora_slope"], analysis["lora_peak_count_ratio"], analysis["lora_peak_spacing_ratio"] = self._analyze_lora(iq_data, iq_freq, iq_padded_fft_abs)

      analysis["lfm_r_squared"], analysis["lfm_slope"] = self._analyze_lfm(iq_freq, iq_freq_mean)

      analysis["cvbs_xcorr_1"], analysis["cvbs_xcorr_2"] = self._analyze_cvbs(iq_acorr_abs)

      analysis["acorr_peak_1_lag_us"], analysis["acorr_peak_1_0_ratio"], analysis["acorr_peak_0_mean_ratio"], analysis["ofdm_data"] = self._analyze_ofdm(iq_acorr_abs, self.ofdm_min_acorr_peak_count)

      analysis["iq_length"] = report["iq_length"]
      analysis["iq_stft_abs"] = iq_stft

      r["analysis"] = analysis
      r["iq_data"] = [[float(np.real(report["iq_data_basebanded"][i])), float(np.imag(report["iq_data_basebanded"][i]))] for i in range(report["iq_data_basebanded"].size)]
      r.pop("iq_data_basebanded")

      t_end = time.time()
      r["processing_time"] = t_end - t_start
      r["time_since_read"] = t_end - timestamp

      #print("mod_analysis: {:.3f}".format(time.time() - t_start))

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

  def _get_stft(self, iq_data):
    num_ffts = int(iq_data.size // self.stft_length)

    iq_stft = np.empty((num_ffts, self.stft_length), dtype=np.complex64)
    for i in range(num_ffts):
      iq_stft[i] = np.fft.fftshift(np.fft.fft(iq_data[i*self.stft_length : (i+1)*self.stft_length]))
    return np.abs(iq_stft)

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

  def _get_fsk_fit_metrics(self, iq_freq, M):
    iq_freq_mean = np.mean(iq_freq)

    y_cluster_2 = iq_freq >= iq_freq_mean

    if M == 2:
      y_cluster = y_cluster_2
    elif M == 3:
      iq_freq_mean_0 = np.mean(iq_freq[y_cluster_2 == 0])
      iq_freq_mean_1 = np.mean(iq_freq[y_cluster_2 == 1])
      y_cluster = np.ones(iq_freq.size, np.uint32)
      y_cluster[iq_freq < iq_freq_mean_0] = 0
      y_cluster[iq_freq > iq_freq_mean_1] = 2
    else:
      raise RuntimeError("invalid M")

    y_cluster_diff  = np.diff(y_cluster)
    ss_residual   = np.zeros(M)
    mu_cluster    = np.zeros(M)
    det_len_hist  = np.zeros(iq_freq.size)
    det_len       = 1

    for i in range(iq_freq.size-1):
      if y_cluster_diff[i] != 0:
        det_len_hist[det_len] += 1
        det_len = 1
      else:
        det_len += 1

    for i in range(M):
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
      r_squared[i], freq_spread[i], det_len_peak[i] = self._get_fsk_fit_metrics(input_iq_freq[i], 2)

    max_i = np.argmax(r_squared)
    return r_squared[max_i], freq_spread[max_i], det_len_peak[max_i]

  def _analyze_bfsk_trunc(self, iq_freq, iq_power, front_dropped_samples, rear_dropped_power_threshold):
    if iq_freq.size < front_dropped_samples*2:
      return 0, 0, 0

    iq_freq_trunc = iq_freq[front_dropped_samples:-1]
    iq_power_trunc = iq_power[front_dropped_samples:-1]

    mean_power = np.mean(iq_power_trunc)
    power_low = iq_power_trunc < (mean_power * rear_dropped_power_threshold)

    first_drop_i = power_low.size - np.argmax(power_low[::-1])

    iq_freq_trunc = iq_freq_trunc[0:first_drop_i]
    if iq_freq_trunc.size < 16:
      return 0, 0, 0

    r_squared, freq_spread, det_len_peak = self._get_fsk_fit_metrics(iq_freq_trunc, 2)
    return r_squared, freq_spread, int(det_len_peak)

  def _analyze_fsk_short(self, iq_freq, M, data_len):
    iq_freq_trunc = iq_freq[0:data_len]
    r_squared, freq_spread, _ = self._get_fsk_fit_metrics(iq_freq_trunc, M)
    return r_squared, freq_spread

  def _analyze_lfm(self, iq_freq, iq_freq_mean):
    freq_x = np.arange(iq_freq.size) * self.dt

    [p_freq, p_info]  = np.polynomial.polynomial.Polynomial.fit(freq_x, iq_freq, deg=1, full=True)
    p_freq            = p_freq.convert().coef

    mean_slope        = p_freq[1]
    ss_residual       = p_info[0][0]
    ss_total          = np.sum((iq_freq - iq_freq_mean)**2)
    r_squared         = 1 - ss_residual/ss_total

    return r_squared, mean_slope

  def _analyze_cvbs(self, iq_acorr_abs):
    if iq_acorr_abs.size not in self.cvbs_xcorr_window_inc_by_len:
      return 0, 0

    w_inc = self.cvbs_xcorr_window_inc_by_len[iq_acorr_abs.size]
    w_exc = self.cvbs_xcorr_window_exc_by_len[iq_acorr_abs.size]

    v_inc = iq_acorr_abs[w_inc[0] : w_inc[1]]
    v_exc = np.concatenate((iq_acorr_abs[w_exc[0] : w_inc[0]], iq_acorr_abs[w_inc[1] : w_exc[1]]))

    inc_max = np.max(v_inc)
    cvbs_xcorr_1 = float(inc_max / iq_acorr_abs[0])
    cvbs_xcorr_2 = float(min(np.mean(v_exc) / inc_max, 1))

    return cvbs_xcorr_1, cvbs_xcorr_2

  def _analyze_ofdm(self, iq_acorr_abs, min_peak_count):
    iq_acorr_trunc = iq_acorr_abs[0:iq_acorr_abs.size//2]

    peak_i, _ = sp.signal.find_peaks(iq_acorr_trunc)

    if len(peak_i) < min_peak_count:
      return 0, 0, 0, []

    peak_v = iq_acorr_trunc[peak_i]
    peak_t = peak_i * self.dt

    sorted_peak_i = np.argsort(peak_v)[::-1]
    sorted_peak_v = peak_v[sorted_peak_i]
    sorted_peak_t = peak_t[sorted_peak_i]

    acorr_peak_1_lag_us = sorted_peak_t[1] / 1e-6
    acorr_peak_1_0_ratio = sorted_peak_v[1] / sorted_peak_v[0]
    acorr_peak_0_mean_ratio = sorted_peak_v[0] / np.mean(sorted_peak_v[1:])

    ofdm_data = {"acorr": [float(x) for x in iq_acorr_trunc], "peak_v": [float(x) for x in peak_v], "peak_t": [float(x) for x in peak_t],
                 "peak_i": [float(x) for x in peak_i], "sorted_peak_i": [float(x) for x in sorted_peak_i], "sorted_peak_v": [float(x) for x in sorted_peak_v], "sorted_peak_t": [float(x) for x in sorted_peak_t]}

    return acorr_peak_1_lag_us, acorr_peak_1_0_ratio, acorr_peak_0_mean_ratio, ofdm_data