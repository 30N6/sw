from pluto_intercept_hw_pkg import *
import numpy as np
#import scipy as sp
import time
import traceback

class pluto_intercept_signal_analysis:
  def __init__(self, config):
    pass
    #self.stft_length = 16
    #self.lora_num_chunks              = config["analysis_config"]["modulation_analysis"]["elrs-lora"]["parameters"]["lora_num_chunks"]
    #self.lora_peak_threshold          = config["analysis_config"]["modulation_analysis"]["elrs-lora"]["parameters"]["lora_peak_threshold"]
    #self.cvbs_xcorr_window_inc        = config["analysis_config"]["modulation_analysis"]["cvbs"]["parameters"]["cvbs_xcorr_window_inc"]
    #self.cvbs_xcorr_window_exc        = config["analysis_config"]["modulation_analysis"]["cvbs"]["parameters"]["cvbs_xcorr_window_exc"]
    ##self.dji_ocusync4_fsk_short_len = config["analysis_config"]["modulation_analysis"]["dji-ocusync-4"]["parameters"]["fsk_short_len"]  #TODO: remove
    #self.ble_trunc_front_samples      = config["analysis_config"]["modulation_analysis"]["ble-bfsk-trunc"]["parameters"]["bfsk_trunc_front_samples"]
    #self.ble_trunc_rear_power_thresh  = 10**(config["analysis_config"]["modulation_analysis"]["ble-bfsk-trunc"]["parameters"]["bfsk_trunc_rear_power_dB"]/10)
    #self.ofdm_min_acorr_peak_count    = config["analysis_config"]["modulation_analysis"]["ofdm-generic"]["parameters"]["ofdm_min_acorr_peak_count"]
    #
    #self.cvbs_xcorr_window_inc_by_len = {}
    #self.cvbs_xcorr_window_exc_by_len = {}
    #for i in range(9, 12):
    #  data_len = 2**i
    #  self.cvbs_xcorr_window_inc_by_len[data_len] = [int(self.cvbs_xcorr_window_inc[0] // self.dt), int(self.cvbs_xcorr_window_inc[1] // self.dt)]
    #  self.cvbs_xcorr_window_exc_by_len[data_len] = [int(self.cvbs_xcorr_window_exc[0] // self.dt), int(self.cvbs_xcorr_window_exc[1] // self.dt)]

  def process_data(self, data):
    t_start = time.time()

    try:
      r = data.copy()
      iq_data = r.pop("iq_data")
      assert (2**int(np.ceil(np.log2(iq_data.size))) == iq_data.size)

      fft_data          = np.fft.fft(iq_data)
      fft_power         = np.square(np.abs(fft_data))
      fft_power_shifted = np.fft.fftshift(fft_power)

      iq_power          = np.square(np.abs(iq_data))
      iq_amplitude      = np.abs(iq_data)

      dt                                  = 1 / r["fs"]
      phase_wrapped                       = np.arctan2(np.imag(iq_data), np.real(iq_data))  #TODO: I/Q ordering
      phase_unwrapped                     = np.unwrap(phase_wrapped)
      iq_freq                             = np.empty(phase_unwrapped.size, dtype=phase_unwrapped.dtype)
      iq_freq[0:phase_unwrapped.size - 1] = (1/(2*np.pi)) * np.diff(phase_unwrapped) / dt
      iq_freq[phase_unwrapped.size - 1]   = 0
      iq_freq_fft                         = np.fft.fft(iq_freq)

      iq_power_avg      = np.mean(iq_power)
      iq_power_peak     = np.max(iq_power)

      iq_amplitude_mean = np.mean(iq_amplitude)
      iq_amplitude_std  = np.std(iq_amplitude)
      iq_amplitude_qtls = np.quantile(iq_amplitude, [0.25, 0.5, 0.75])

      iq_freq_mean      = np.mean(iq_freq)
      iq_freq_std       = np.std(iq_freq)

      iq_data_acorr_abs = np.abs(np.fft.ifft(fft_power))
      iq_freq_acorr_abs = np.abs(np.fft.ifft(np.square(np.abs(iq_freq_fft))))

      bandwidth         = self._get_bandwidth_data(fft_power_shifted, r["fs"])

      amplitude_hist_count, amplitude_hist_edges = np.histogram(iq_amplitude, 128)
      frequency_hist_count, frequency_hist_edges = np.histogram(iq_freq, 128)

      r["iq_data_I"] = iq_data.real
      r["iq_data_Q"] = iq_data.imag

      features = {}
      features["power_avg"]             = iq_power_avg
      features["power_peak"]            = iq_power_peak
      features["power_papr"]            = iq_power_peak / iq_power_avg
      features["amplitude_mean"]        = iq_amplitude_mean
      features["amplitude_median"]      = iq_amplitude_qtls[1]
      features["amplitude_std"]         = iq_amplitude_std
      features["amplitude_cv"]          = iq_amplitude_std / iq_amplitude_mean
      features["amplitude_hist_count"]  = amplitude_hist_count
      features["amplitude_hist_edges"]  = amplitude_hist_edges
      features["amplitude_iqr_ratio"]   = (iq_amplitude_qtls[2] - iq_amplitude_qtls[0]) / iq_amplitude_qtls[1]
      features["frequency_mean"]        = iq_freq_mean
      features["frequency_std"]         = iq_freq_std
      features["frequency_hist_count"]  = frequency_hist_count
      features["frequency_hist_edges"]  = frequency_hist_edges
      features["bandwidth_3dB"]         = bandwidth[0]
      features["bandwidth_6dB"]         = bandwidth[1]
      features["bandwidth_10dB"]        = bandwidth[2]
      features["iq_acorr_abs"]          = iq_data_acorr_abs
      features["frequency_acorr_abs"]   = iq_freq_acorr_abs

      #features["frequency_data"]        = iq_freq #TODO: remove

      r["timestamp_proc_start"] = t_start
      r["timestamp_proc_end"] = time.time()
      r["features"] = features

      return r

      #iq_data = report["iq_data"]
      #timestamp = report["sw_timestamp"]
      #
      #padded_length = 2**int(np.ceil(np.log2(iq_data.size)))
      #samples_to_pad = padded_length - iq_data.size
      #iq_data_padded = np.pad(iq_data, (0, samples_to_pad))
      #
      #phase_wrapped     = np.arctan2(np.imag(iq_data), np.real(iq_data))  #TODO: I/Q ordering
      #phase_unwrapped   = np.unwrap(phase_wrapped)
      #iq_freq           = (1/(2*np.pi)) * np.diff(phase_unwrapped) / self.dt
      #iq_freq_mean      = np.mean(iq_freq)
      #iq_padded_fft     = np.abs(np.fft.fftshift(np.fft.fft(iq_data_padded)))
      #iq_padded_fft_abs = np.abs(iq_padded_fft)
      #iq_power          = np.square(np.real(iq_data)) + np.square(np.imag(iq_data))
      #iq_stft           = self._get_stft(iq_data)
      #
      #iq_padded_fft_conj  = np.conjugate(iq_padded_fft)
      #iq_padded_fft_prod  = iq_padded_fft * iq_padded_fft_conj
      #iq_acorr_abs        = np.abs(np.fft.ifft(iq_padded_fft_prod))
      #
      #r = report.copy()
      #r.pop("iq_data")
      #r.pop("iq_length")
      #
      #analysis = {}
      #analysis["power_mean"] = float(np.mean(iq_power))
      #analysis["power_max"] = float(np.max(iq_power))
      #analysis["fft_mean"], analysis["fft_std"] = self._get_fft_stats(iq_padded_fft_abs)
      #
      #analysis["bfsk_r_squared"], analysis["bfsk_freq_spread"], analysis["bfsk_len_peak"] = self._analyze_bfsk(iq_freq)
      #analysis["bfsk_trunc_r_squared"], analysis["bfsk_trunc_freq_spread"], analysis["bfsk_trunc_len_peak"] = self._analyze_bfsk_trunc(iq_freq, iq_power, self.ble_trunc_front_samples, self.ble_trunc_rear_power_thresh)
      #
      ##analysis["bfsk_short_r_squared"], analysis["bfsk_short_freq_spread"] = self._analyze_fsk_short(iq_freq, 2, self.dji_ocusync4_fsk_short_len) #TODO: remove
      ##analysis["tfsk_short_r_squared"], analysis["tfsk_short_freq_spread"] = self._analyze_fsk_short(iq_freq, 3, self.dji_ocusync4_fsk_short_len) #TODO: remove
      ##analysis["tfsk_bfsk_short_r_squared_ratio"] = analysis["tfsk_short_r_squared"] / analysis["bfsk_short_r_squared"] #TODO: remove
      #
      #analysis["lora_r_squared"], analysis["lora_slope"], analysis["lora_peak_count_ratio"], analysis["lora_peak_spacing_ratio"] = self._analyze_lora(iq_data, iq_freq, iq_padded_fft_abs)
      #
      #analysis["lfm_r_squared"], analysis["lfm_slope"] = self._analyze_lfm(iq_freq, iq_freq_mean)
      #
      #analysis["cvbs_xcorr_1"], analysis["cvbs_xcorr_2"] = self._analyze_cvbs(iq_acorr_abs)
      #
      #analysis["acorr_peak_1_lag_us"], analysis["acorr_peak_1_0_ratio"], analysis["acorr_peak_0_mean_ratio"], analysis["ofdm_data"] = self._analyze_ofdm(iq_acorr_abs, self.ofdm_min_acorr_peak_count)
      #
      #analysis["iq_length"] = report["iq_length"]
      #analysis["iq_stft_abs"] = iq_stft
      #
      #r["analysis"] = analysis
      #r["iq_data"] = [[float(np.real(report["iq_data_basebanded"][i])), float(np.imag(report["iq_data_basebanded"][i]))] for i in range(report["iq_data_basebanded"].size)]
      #r.pop("iq_data_basebanded")
      #
      #t_end = time.time()
      #r["processing_time"] = t_end - t_start
      #r["time_since_read"] = t_end - timestamp
      #
      ##print("mod_analysis: {:.3f}".format(time.time() - t_start))
      #
      ##if (analysis["lora_r_squared"] > 0.7):
      ##  print("LORA: [{}] {:.3f} {:.1f} {:.2f} {:.2f} -- {:.6f} {:.6f}".format(r["hw_timestamp"], analysis["lora_r_squared"], analysis["lora_slope"] / (1e3/1e-6), analysis["lora_peak_count_ratio"], analysis["lora_peak_spacing_ratio"], t_end - t_start, t_end - timestamp))
      ##if (analysis["lfm_r_squared"] > 0.7):
      ##  print("LFM: [{}] {:.3f} {:.1f}".format(r["hw_timestamp"], analysis["lfm_r_squared"], analysis["lfm_slope"] / (1e3/1e-6)))
      #return r

    except Exception:
      s = traceback.format_exc()
      print(s)
      return {"exception": s}

    #print("FSK: {:.3f} {:.1f}".format(fsk_r_squared, fsk_freq_spread))
    #print("FSK: {} {}".format(fsk_r_squared, fsk_freq_spread))

  def _get_bandwidth_data(self, fft_power, fs):
    p = np.argmax(fft_power)

    bandwidth = [0, 0, 0]
    threshold = [fft_power[p] * 0.5, fft_power[p] * 0.25, fft_power[p] * 0.01]
    upper_done = [False, False, False]
    upper_index = [0, 0, 0]
    lower_done = [False, False, False]
    lower_index = [0, 0, 0]

    idx = p
    while (idx < fft_power.size) and not(all(upper_done)):
      for j in range(len(threshold)):
        if (fft_power[idx] < threshold[j]) and not(upper_done[j]):
          upper_done[j] = True
          upper_index[j] = idx
      idx += 1

    idx = p
    while (idx >= 0) and not(all(lower_done)):
      for j in range(len(threshold)):
        if (fft_power[idx] < threshold[j]) and not(lower_done[j]):
          lower_done[j] = True
          lower_index[j] = idx
      idx -= 1

    for i in range(len(threshold)):
      assert not(upper_done[i] ^ lower_done[i])
      if upper_done[i] and lower_done[i]:
        bandwidth[i] = fs * (1/fft_power.size) * (upper_index[i] - lower_index[i] + 1)

    return bandwidth

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

