import struct
from pluto_esm_hw_pkg import *


def populate_dwell_entry(config, entry_index, center_freq, dwell_time, fast_lock_profile):
  channel_spacing_MHz = (ADC_CLOCK_FREQUENCY / ESM_NUM_CHANNELS_NARROW) / 1e6
  assert (channel_spacing_MHz == config["dwell_config"]["channel_step"])
  channel_sampling_freq_Mhz = channel_spacing_MHz * CHANNELIZER_OVERSAMPLING
  channel_sampling_time_us = 1 / channel_sampling_freq_Mhz

  center_index = ESM_NUM_CHANNELS_NARROW // 2
  channel_mask_initial = 0x0FFFFFFFFFFFFFF0
  channel_mask_final = 0
  PW_range = [10000, 0]
  min_threshold_dB = 50

  for i in range(ESM_NUM_CHANNELS_NARROW):
    if (channel_mask_initial & (1 << i)) == 0:
      continue
    channel_freq = center_freq + (i - center_index)
    for emitter in config["emitter_config"]["pulsed_emitters"]:
      if (channel_freq >= emitter["freq_range"][0]) and (channel_freq <= emitter["freq_range"][1]):
        channel_mask_final  = channel_mask_final | (1 << i)
        min_threshold_dB    = min(min_threshold_dB, emitter["threshold_dB"])
        PW_range[0]         = min(PW_range[0], emitter["PW_range"][0])
        PW_range[1]         = max(PW_range[1], emitter["PW_range"][1])

  min_threshold_linear = 10 ** (min_threshold_dB / 10)
  threshold_shift = 0
  while ((1 << threshold_shift) < min_threshold_linear):
    threshold_shift += 1
  assert (threshold_shift < 31)

  duration_in_cycles = int(dwell_time / FAST_CLOCK_PERIOD)
  min_pd = int((0.5 * PW_range[0]) // channel_sampling_time_us)

  return esm_message_dwell_entry(entry_index, entry_index, center_freq, duration_in_cycles, 0, fast_lock_profile, threshold_shift, 31, channel_mask_final, 0xFF, min_pd)

class esm_message_dwell_entry:
  def __init__(self, entry_index, tag, freq, duration, gain, fast_lock_profile, thresh_shift_n, thresh_shift_w, chan_mask_n, chan_mask_w, min_pd):
    assert (entry_index < ESM_NUM_DWELL_ENTRIES)
    assert (tag <= 0xFFFF)
    assert (freq <= 0xFFFF)
    assert (duration <= 0xFFFFFFFF)
    assert (gain <= 0x7F)
    assert (fast_lock_profile < ESM_NUM_FAST_LOCK_PROFILES)
    assert (thresh_shift_n <= 0x1F)
    assert (thresh_shift_w <= 0x1F)
    assert (chan_mask_n <= 0xFFFFFFFFFFFFFFFF)
    assert (chan_mask_w <= 0xFF)
    assert (min_pd <= 0xFFFF)

    self.entry_index            = entry_index
    self.tag                    = tag
    self.frequency              = int(round(freq))
    self.duration               = duration
    self.gain                   = gain
    self.fast_lock_profile      = fast_lock_profile
    self.threshold_shift_narrow = thresh_shift_n
    self.threshold_shift_wide   = thresh_shift_w
    self.channel_mask_narrow     = chan_mask_n
    self.channel_mask_wide       = chan_mask_w
    self.min_pulse_duration      = min_pd

  def __str__(self):
    return "dwell_entry: idx={} tag={} freq={} len={} flp={} thresh={} mask={:016X}, mpd={}".format(self.entry_index, self.tag, self.frequency, self.duration, self.fast_lock_profile, self.threshold_shift_narrow, self.channel_mask_narrow, self.min_pulse_duration)
  def __repr__(self):
    return self.__str__()

  def pack(self):
    return PACKED_ESM_MESSAGE_DWELL_ENTRY.pack(self.entry_index, self.tag, self.frequency, self.duration, self.gain, self.fast_lock_profile, self.threshold_shift_narrow, self.threshold_shift_wide, self.channel_mask_narrow, self.channel_mask_wide, self.min_pulse_duration)

  @staticmethod
  def default_dwell():
    return esm_message_dwell_entry(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)

  @staticmethod
  def default_scan_dwell(entry_index, tag, freq, duration, fast_lock_profile):
    duration_in_cycles = int(duration / FAST_CLOCK_PERIOD)
    min_pd = 1
    return esm_message_dwell_entry(entry_index, tag, freq, duration_in_cycles, 0, fast_lock_profile, 7, 6, 0x0FFFFFFFFFFFFFF0, 0xFF, min_pd)

  @staticmethod
  def from_dict(d):
    return esm_message_dwell_entry(d["entry_index"], d["tag"], d["frequency"], d["duration"], d["gain"], d["fast_lock_profile"],
                                   d["threshold_narrow"], d["threshold_wide"], d["channel_mask_narrow"], d["channel_mask_wide"], d["min_pulse_duration"])

class esm_dwell_instruction:
  def __init__(self, valid, global_counter_check, global_counter_dec, skip_pll_prelock_wait, skip_pll_lock_check, skip_pll_postlock_wait, repeat_count, entry_index, next_instruction_index):
    assert (valid <= 1)
    assert (global_counter_check <= 1)
    assert (global_counter_dec <= 1)
    assert (skip_pll_prelock_wait <= 1)
    assert (skip_pll_lock_check <= 1)
    assert (skip_pll_postlock_wait <= 1)
    assert (repeat_count < 16)
    assert (entry_index < ESM_NUM_DWELL_ENTRIES)
    assert (next_instruction_index < ESM_NUM_DWELL_INSTRUCTIONS)

    self.valid                  = valid
    self.global_counter_check   = global_counter_check
    self.global_counter_dec     = global_counter_dec
    self.skip_pll_prelock_wait  = skip_pll_prelock_wait
    self.skip_pll_lock_check    = skip_pll_lock_check
    self.skip_pll_postlock_wait = skip_pll_postlock_wait
    self.repeat_count           = repeat_count
    self.entry_index            = entry_index
    self.next_instruction_index = next_instruction_index

  def pack(self):
    command_byte = self.valid | (self.global_counter_check << 1) | (self.global_counter_dec << 2) | \
                   (self.skip_pll_prelock_wait << 3) | (self.skip_pll_lock_check << 4) | (self.skip_pll_postlock_wait << 5)
    return PACKED_DWELL_INSTRUCTION.pack(command_byte, self.repeat_count, self.entry_index, self.next_instruction_index)

class esm_message_dwell_program:
  def __init__(self, enable_program, enable_delayed_start, global_counter_init, delayed_start_time, instructions):
    assert (enable_program <= 1)
    assert (enable_delayed_start <= 1)
    assert (global_counter_init <= 0xFFFFFFFF)
    assert (delayed_start_time <= 0xFFFFFFFFFFFFFFFF)
    assert (len(instructions) <= ESM_NUM_DWELL_INSTRUCTIONS)

    self.enable_program       = enable_program
    self.enable_delayed_start = enable_delayed_start
    self.global_counter_init  = global_counter_init #TODO: global counter reporting
    self.delayed_start_time   = delayed_start_time
    self.instructions         = instructions

  def pack(self):
    packed_data = PACKED_DWELL_PROGRAM.pack(self.enable_program, self.enable_delayed_start, self.global_counter_init, self.delayed_start_time)
    for i in range(len(self.instructions)):
      packed_data += self.instructions[i].pack()
    return packed_data

class esm_dwell_controller:
  def __init__(self, config_writer):
    self.config_writer = config_writer
    self.dwells_by_tag = {}
    self.current_dwell_program = []

  def send_dwell_entry(self, dwell_entry):
    self.dwells_by_tag[dwell_entry.tag] = dwell_entry
    return self.config_writer.send_module_data(ESM_MODULE_ID_DWELL_CONTROLLER, ESM_CONTROL_MESSAGE_TYPE_DWELL_ENTRY, dwell_entry.pack(), True)

  def send_dwell_program(self, dwell_program):
    self.current_dwell_program = dwell_program
    return self.config_writer.send_module_data(ESM_MODULE_ID_DWELL_CONTROLLER, ESM_CONTROL_MESSAGE_TYPE_DWELL_PROGRAM, dwell_program.pack(), True)
