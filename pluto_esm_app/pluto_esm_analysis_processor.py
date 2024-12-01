import pluto_esm_data_recorder
import pluto_esm_pdw_modulation_analysis
from pluto_esm_hw_pkg import *
import time
import numpy as np

class pluto_esm_analysis_processor:
  def __init__(self, logger, log_dir, config):
    self.logger   = logger
    self.recorder = pluto_esm_data_recorder.pluto_esm_data_recorder(log_dir, "analysis", config["analysis_config"]["enable_pdw_recording"])
    self.config   = config

    self.pdw_processor        = pluto_esm_pdw_processor(logger)
    self.pulsed_tracker       = pluto_esm_pulsed_emitter_tracker(logger, self.pdw_processor, config)
    self.modulation_analyzer  = pluto_esm_pdw_modulation_analysis.pluto_esm_pdw_modulation_analysis(config["analysis_config"]["modulation_analysis"])

    self.confirmed_emitters_to_render = []

    self.pending_dwell_reports        = []
    self.pending_pdw_summary_reports  = []
    self.pending_pdw_pulse_reports    = []
    self.pending_combined_data        = []

    self.center_channel_index = (ESM_NUM_CHANNELS_NARROW // 2)
    self.channel_spacing      = (ADC_CLOCK_FREQUENCY / ESM_NUM_CHANNELS_NARROW) / 1e6

    self.emitter_update_interval = 0.1
    self.last_emitter_update_time = 0

  def _merge_pdws(self, combined_data):
    dwell_report = combined_data["dwell_report"]["dwell_report"]
    dwell_freq = combined_data["dwell_report"]["dwell_data"].frequency

    for pdw in combined_data["pdw_pulse_reports"]:
      pulse_channel = pdw["pulse_channel"]
      pdw["channel_frequency"]      = dwell_freq + (pulse_channel - self.center_channel_index) * self.channel_spacing
      pdw["dwell_channel_entry"]    = dwell_report["channel_data"][pulse_channel]
      pdw["dwell_threshold_shift"]  = dwell_report["threshold_shift_narrow"]

      if pdw["buffered_frame_valid"]:
        mod_data = self.modulation_analyzer.check_intrapulse_modulation(pdw["pulse_duration"], pdw["buffered_frame_data"])
      else:
        mod_data = None
      pdw["modulation_data"] = mod_data

      self.recorder.log(pdw)

    #self.pdw_processor.submit_pdws_for_dwell(combined_data["pdw_pulse_reports"])
    self.recorder.flush()

  def _populate_dwell_channels(self, combined_data):
    dwell_freq = combined_data["dwell_report"]["dwell_data"].frequency
    dwell_num_samples = combined_data["dwell_report"]["dwell_report"]["num_samples"]
    channel_mask = combined_data["dwell_report"]["dwell_data"].hw_dwell_entry.channel_mask_narrow

    num_samples_by_channel = {}
    for i in range(ESM_NUM_CHANNELS_NARROW):
      if (channel_mask & (1 << i)) == 0:
        continue
      channel_freq = dwell_freq + (i - self.center_channel_index) * self.channel_spacing
      num_samples_by_channel[channel_freq] = dwell_num_samples
    combined_data["dwell_num_samples_for_pdw"] = num_samples_by_channel

  def _process_matched_reports(self):
    while len(self.pending_combined_data) > 0:
      combined_data         = self.pending_combined_data.pop(0)
      expected_pulse_count  = combined_data["pdw_summary_report"]["dwell_pulse_total_count"] - combined_data["pdw_summary_report"]["dwell_pulse_drop_count"]
      actual_pulse_count    = len(combined_data["pdw_pulse_reports"])
      assert (expected_pulse_count == actual_pulse_count)
      self.logger.log(self.logger.LL_INFO, "[analysis_processor] _process_matched_reports: seq_num={} freq={} num_pulses={}".format(combined_data["pdw_summary_report"]["dwell_seq_num"],
                                                                                                                                    combined_data["dwell_report"]["dwell_data"].frequency,
                                                                                                                                    actual_pulse_count))
      self._merge_pdws(combined_data)
      self._populate_dwell_channels(combined_data)
      self.pdw_processor.submit_dwell_data(combined_data)

  def _match_dwell_reports(self):
    if (len(self.pending_dwell_reports) == 0) or (len(self.pending_pdw_summary_reports) == 0):
      return

    pdw_seq_num   = self.pending_pdw_summary_reports[0]["pdw_summary_report"]["dwell_seq_num"]
    dwell_seq_num = self.pending_dwell_reports[0]["dwell_report"]["dwell_seq_num"]

    if pdw_seq_num != dwell_seq_num:
      assert (pdw_seq_num > dwell_seq_num)
      self.logger.log(self.logger.LL_WARN, "[analysis_processor] _match_dwell_reports: missed PDW dwell detected! dwell_seq_num={} pdw_seq_num={}".format(dwell_seq_num, pdw_seq_num))
      self.pending_dwell_reports.pop(0)
      return

    matched_pulse_reports = []
    while len(self.pending_pdw_pulse_reports) > 0:
      pdw_dwell_seq_num = self.pending_pdw_pulse_reports[0]["pdw_pulse_report"]["dwell_seq_num"]
      if pdw_dwell_seq_num == dwell_seq_num:
        matched_pulse_reports.append(self.pending_pdw_pulse_reports.pop(0)["pdw_pulse_report"])
      else:
        assert(pdw_dwell_seq_num > dwell_seq_num)
        break

    self.pending_combined_data.append({"dwell_report": self.pending_dwell_reports.pop(0),
                                       "pdw_summary_report": self.pending_pdw_summary_reports.pop(0)["pdw_summary_report"],
                                       "pdw_pulse_reports": matched_pulse_reports})

  def _update_tracked_emitters(self):
    now = time.time()
    if (now - self.last_emitter_update_time) < self.emitter_update_interval:
      return
    self.last_emitter_update_time = now

    self.confirmed_emitters_to_render = self.pulsed_tracker.confirmed_emitters.copy()

  def submit_report(self, report):
    if "pdw_pulse_report" in report:
      self.pending_pdw_pulse_reports.append(report)
    elif "pdw_summary_report" in report:
      self.pending_pdw_summary_reports.append(report)
    elif "dwell_report" in report:
      self.pending_dwell_reports.append(report)

  def update(self):
    self.pdw_processor.update()
    self.pulsed_tracker.update()
    self._match_dwell_reports()
    self._process_matched_reports()
    self._update_tracked_emitters()

  def shutdown(self, reason):
    self.recorder.shutdown(reason)


class pluto_esm_pdw_processor:
  def __init__(self, logger):
    self.logger = logger

    self.dwell_history_pdw = []
    self.dwell_history_accum = []
    self.max_dwell_age = 60 #TODO: config?

    #TODO: config?
    #self.hist_pd  = histogram_multi_level([0, 16383], [1, 4, 16, 64])
    #self.hist_pri = histogram_multi_level([0, 65535], [1, 8, 64, 256])
    #self.hist_pri_pd = histogram_2d([65536, 1024])
    self.hist_pri         = histogram_1d(65536)
    self.hist_pd          = histogram_1d(1024)
    self.dwell_time_accum = {}

    self.scale_factor_pd  = ((ESM_NUM_CHANNELS_NARROW / CHANNELIZER_OVERSAMPLING) * ADC_CLOCK_PERIOD) / 1.0e-6
    self.scale_factor_toa = FAST_CLOCK_PERIOD / 1.0e-6

  def submit_dwell_data(self, combined_dwell_data):
    now = time.time()

    pdws              = combined_dwell_data["pdw_pulse_reports"]
    dwell_num_samples = combined_dwell_data["dwell_num_samples_for_pdw"]

    dwell_freqs = np.unique([p["channel_frequency"] for p in pdws])
    for channel_freq in dwell_freqs:
      channel_pdws        = [p for p in pdws if (p["channel_frequency"] == channel_freq)]
      channel_num_samples = dwell_num_samples[channel_freq]

      pulse_duration_raw  = np.asarray([p["pulse_duration"] for p in channel_pdws])
      pulse_duration      = pulse_duration_raw * self.scale_factor_pd
      pulse_toa           = np.asarray([p["pulse_start_time"] for p in channel_pdws]) * self.scale_factor_toa
      pulse_pri           = np.diff(pulse_toa)
      #pulse_power         = np.asarray([p["pulse_power_accum"] for p in channel_pdws]) / pulse_duration_raw

      for i in range(len(channel_pdws) - 1):
        channel_pdws[i]["pulse_pri"]      = pulse_pri[i]
        channel_pdws[i]["processor_time"] = now
      channel_pdws[-1]["pulse_pri"]       = -1
      channel_pdws[-1]["processor_time"]  = now

      self.dwell_history_pdw.append({"time": now,
                                 "pdws": channel_pdws,
                                 "channel_freq": channel_freq,
                                 "pulse_duration": pulse_duration,
                                 "pulse_pri": pulse_pri,
                                 #"pulse_power": pulse_power,
                                 "dwell_num_samples": channel_num_samples})
      self.hist_pd.add_dwell_pdws(channel_freq, pulse_duration)
      self.hist_pri.add_dwell_pdws(channel_freq, pulse_pri)

    for channel_freq in dwell_num_samples:
      if channel_freq not in self.dwell_time_accum:
        self.dwell_time_accum[channel_freq] = 0
      self.dwell_time_accum[channel_freq] += dwell_num_samples[channel_freq] #* FAST_CLOCK_PERIOD
    self.dwell_history_accum.append({"time": now, "dwell_num_samples": dwell_num_samples})

  def _scrub_history(self):
    now = time.time()

    while len(self.dwell_history_pdw) > 0:
      if (now - self.dwell_history_pdw[0]["time"]) > self.max_dwell_age:
        removed_dwell = self.dwell_history_pdw.pop(0)
        self.hist_pd.remove_dwell_pdws(removed_dwell["channel_freq"], removed_dwell["pulse_duration"])
        self.hist_pri.remove_dwell_pdws(removed_dwell["channel_freq"], removed_dwell["pulse_pri"])
      else:
        break

    while len(self.dwell_history_accum) > 0:
      if (now - self.dwell_history_accum[0]["time"]) > self.max_dwell_age:
        removed_dwell = self.dwell_history_accum.pop(0)
        for freq in removed_dwell["dwell_num_samples"]:
          self.dwell_time_accum[freq] -= removed_dwell["dwell_num_samples"][freq]
      else:
        break

  def update(self):
    self._scrub_history()

#TODO: separate file
class pluto_esm_pulsed_emitter_tracker:
  def __init__(self, logger, pdw_processor, config):
    self.logger = logger
    self.pdw_processor = pdw_processor

    self.pulsed_emitter_config        = config["emitter_config"]["pulsed_emitters"]
    self.modulation_threshold         = config["analysis_config"]["modulation_threshold"]
    self.pd_range_scaling             = config["analysis_config"]["pulsed_emitter_search"]["PW_range_scaling"]
    self.pri_range_scaling            = config["analysis_config"]["pulsed_emitter_search"]["PRI_range_scaling"]
    self.expected_pulse_count_factor  = config["analysis_config"]["pulsed_emitter_search"]["expected_pulse_count"]

    self.last_update_time = 0

    #TODO: config?
    self.emitter_update_interval = 0.5
    self.min_matched_pulses       = 40
    self.max_emitter_age          = 30
    self.max_pdw_age_to_confirm   = 20

    self.confirmed_emitters = []

  def update(self):
    now = time.time()
    if (now - self.last_update_time) < self.emitter_update_interval:
      return
    self.last_update_time = now

    self._search_emitters()
    self._scrub_emitters()

  def _confirm_emitter(self, freq, expected_pd_range, expected_pri_range, expected_pulse_count):
    combined_pri = np.empty(0)
    combined_pd = np.empty(0)
    combined_pdw = []

    for dwell in self.pdw_processor.dwell_history_pdw:
      if dwell["channel_freq"] != freq:
        continue

      combined_pri = np.concatenate([combined_pri, dwell["pulse_pri"]])
      combined_pd = np.concatenate([combined_pd, dwell["pulse_duration"][:-1]])
      combined_pdw.extend(dwell["pdws"][:-1])

    #print("_confirm_emitter: pri={}".format(combined_pri))

    matching_pri = (combined_pri > expected_pri_range[0]) & (combined_pri < expected_pri_range[1])
    matching_pd = (combined_pd > expected_pd_range[0]) & (combined_pd < expected_pd_range[1])
    matching_all = matching_pri & matching_pd

    num_matched_pulses = np.sum(matching_all)
    matching_pdws = [combined_pdw[i] for i in range(len(combined_pdw)) if matching_all[i]]

    if len(matching_pdws) > 0:
      min_pdw_age = time.time() - matching_pdws[-1]["processor_time"]
    else:
      min_pdw_age = -1

    confirmed = (num_matched_pulses >= expected_pulse_count) and (num_matched_pulses >= self.min_matched_pulses) and (min_pdw_age < self.max_pdw_age_to_confirm)

    return confirmed, matching_pdws, min_pdw_age

  def _update_confirmed_emitter(self, freq, emitter, matched_pulses):
    now = time.time()

    matched_emitter = None
    for entry in self.confirmed_emitters:
      if (entry["freq"] == freq) and (entry["name"] == emitter["name"]):
        matched_emitter = entry
        break

    if matched_emitter is None:
      matched_emitter = {"freq": freq,
                         "name": emitter["name"],
                         #"pdws": matched_pulses,
                         "pulses_in_window": len(matched_pulses),
                         "pdw_time_initial": matched_pulses[0]["processor_time"],
                         "pdw_time_final": matched_pulses[-1]["processor_time"]}
      self.confirmed_emitters.append(matched_emitter)
      self.logger.log(self.logger.LL_INFO, "[pulsed_tracker] _update_confirmed_emitter: NEW - [{}/{}] matched_pulses={}".format(emitter["name"], freq, len(matched_pulses)))
    else:
      #matched_emitter["pdws"] = matched_pulses
      matched_emitter["pulses_in_window"] = len(matched_pulses)
      matched_emitter["pdw_time_final"] = matched_pulses[-1]["processor_time"]

    pulse_duration  = np.asarray([p["pulse_duration"] for p in matched_pulses])
    pulse_power     = np.asarray([p["pulse_power_accum"] for p in matched_pulses]) / pulse_duration
    pulse_pri       = np.asarray([p["pulse_pri"] for p in matched_pulses if p["pulse_pri"] > 0])

    matched_emitter["power_mean"]           = np.mean(pulse_power)
    matched_emitter["power_max"]            = np.max(pulse_power)
    matched_emitter["power_std"]            = np.std(pulse_power)
    matched_emitter["pulse_power"]          = pulse_power
    matched_emitter["pulse_duration"]       = pulse_duration
    matched_emitter["pulse_duration_mean"]  = np.mean(pulse_duration)
    matched_emitter["pulse_duration_std"]   = np.std(pulse_duration)
    matched_emitter["sorted_pulse_pri"]     = np.sort(pulse_pri)

    mod_data = [p["modulation_data"] for p in matched_pulses if (p["modulation_data"] is not None)]
    mod_FM   = [md for md in mod_data if md["modulation_type"] == "FM"]

    if (len(mod_data) > 0) and ((len(mod_FM) / len(mod_data)) > self.modulation_threshold):
      mean_slope      = np.mean([md["LFM_slope"] for md in mod_FM])
      mean_r_squared  = np.mean([md["LFM_r_squared"] for md in mod_FM])
      matched_emitter["modulation"] = {"modulation_type": "FM", "pulses_analyzed": len(mod_data), "pulses_with_mod": len(mod_FM), "FM_mean_slope": mean_slope, "FM_mean_r_squared": mean_r_squared}
    else:
      matched_emitter["modulation"] = None

    self.logger.log(self.logger.LL_INFO, "[pulsed_tracker] _update_confirmed_emitter: [{}/{}] matched_pulses={} power_mean={:.1f} power_max={:.1f} power_std={:.1f} age={:.1f}".format(emitter["name"], freq, len(matched_pulses),
      matched_emitter["power_mean"], matched_emitter["power_max"], matched_emitter["power_std"], matched_emitter["pdw_time_final"] - matched_emitter["pdw_time_initial"]))

  def _search_emitters(self):
    for freq in sorted(self.pdw_processor.hist_pd.data_count):
      accumulated_dwell_time = self.pdw_processor.dwell_time_accum[freq] * FAST_CLOCK_PERIOD

      for emitter in self.pulsed_emitter_config:
        if (freq < emitter["freq_range"][0]) or (freq > emitter["freq_range"][1]):
          continue

        expected_pulse_count  = (accumulated_dwell_time / (emitter["PRI_range"][1] * 1e-6)) * self.expected_pulse_count_factor
        expected_pd_range     = [emitter["PW_range"][0]  * self.pd_range_scaling[0],  emitter["PW_range"][1]  * self.pd_range_scaling[1]]
        expected_pri_range    = [emitter["PRI_range"][0] * self.pri_range_scaling[1], emitter["PRI_range"][1] * self.pri_range_scaling[1]]

        #TODO: skip the histogram and check the pulses directly?
        num_matching_pd   = self.pdw_processor.hist_pd.get_count_in_range(freq, expected_pd_range)
        num_matching_pri  = self.pdw_processor.hist_pri.get_count_in_range(freq, expected_pri_range)

        #print("freq={} expected_pulse_count={} num_matching_pd={}-{} num_matching_pri={}-{}".format(freq, expected_pulse_count, num_matching_pd, (num_matching_pd > expected_pulse_count), num_matching_pri, (num_matching_pri > expected_pulse_count)))

        if (num_matching_pd > expected_pulse_count) and (num_matching_pri > expected_pulse_count):
          self.logger.log(self.logger.LL_INFO, "[pulsed_tracker] _search_emitters: initial candidate - name={} freq={} dt_accum={:.3f} exp_pulses={:.1f} hist_count={} match_pd={} match_pri={}".format(emitter["name"],
            freq, accumulated_dwell_time, expected_pulse_count, self.pdw_processor.hist_pd.data_count[freq], num_matching_pd, num_matching_pri))

          confirmed, matched_pulses, min_pdw_age = self._confirm_emitter(freq, expected_pd_range, expected_pri_range, expected_pulse_count)
          if confirmed:
            self._update_confirmed_emitter(freq, emitter, matched_pulses)

  def _scrub_emitters(self):
    now = time.time()
    emitters_to_keep = []
    for entry in self.confirmed_emitters:
      if (now - entry["pdw_time_final"]) < self.max_emitter_age:
        emitters_to_keep.append(entry)
      else:
        self.logger.log(self.logger.LL_INFO, "[pulsed_tracker] _scrub_emitters: confirmed emitter timeout - {}".format(entry))

    self.confirmed_emitters = emitters_to_keep


class histogram_1d:
  def __init__(self, bin_count):
    self.bin_count = bin_count
    self.hist_count = {}
    self.data_count = {}

  def add_dwell_pdws(self, freq, data):
    if freq not in self.hist_count:
      self.hist_count[freq] = np.zeros(self.bin_count, dtype=np.uint32)
      self.data_count[freq] = 0

    data_index = data.astype(np.uint32)
    data_index[data_index >= self.bin_count] = self.bin_count - 1
    self.hist_count[freq][data_index] += 1
    self.data_count[freq] += len(data)

  def remove_dwell_pdws(self, freq, data):
    data_index = data.astype(np.uint32)
    data_index[data_index >= self.bin_count] = self.bin_count - 1
    self.hist_count[freq][data_index] -= 1
    self.data_count[freq] -= len(data)

  def get_count_in_range(self, freq, hist_range):
    i_start = int(min(hist_range[0], self.bin_count - 1))
    i_end   = int(min(hist_range[1], self.bin_count))
    assert (i_end > i_start)

    return np.sum(self.hist_count[freq][i_start:i_end])
