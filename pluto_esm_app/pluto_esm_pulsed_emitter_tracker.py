import time
import numpy as np

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
