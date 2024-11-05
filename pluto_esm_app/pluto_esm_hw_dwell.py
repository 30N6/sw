import struct
from pluto_esm_hw_pkg import *

class esm_message_dwell_entry:
  def __init__(self, entry_index, tag, freq, duration, gain, fast_lock_profile, thresh_n, thresh_w, chan_mask_n, chan_mask_w, min_pd):
    assert (entry_index < ESM_NUM_DWELL_ENTRIES)
    assert (tag <= 0xFFFF)
    assert (freq <= 0xFFFF)
    assert (duration <= 0xFFFFFFFF)
    assert (gain <= 0x7F)
    assert (fast_lock_profile < ESM_NUM_FAST_LOCK_PROFILES)
    assert (thresh_n <= 0xFFFFFFFF)
    assert (thresh_w <= 0xFFFFFFFF)
    assert (chan_mask_n <= 0xFFFFFFFFFFFFFFFF)
    assert (chan_mask_w <= 0xFF)
    assert (min_pd <= 0xFFFF)

    self.entry_index          = entry_index
    self.tag                  = tag
    self.frequency            = freq
    self.duration             = duration
    self.gain                 = gain
    self.fast_lock_profile    = fast_lock_profile
    self.threshold_narrow     = thresh_n
    self.threshold_wide       = thresh_w
    self.channel_mask_narrow  = chan_mask_n
    self.channel_mask_wide    = chan_mask_w
    self.min_pulse_duration   = min_pd

  def pack(self):
    return PACKED_ESM_MESSAGE_DWELL_ENTRY.pack(self.entry_index, self.tag, self.frequency, self.duration, self.gain, self.fast_lock_profile, self.threshold_narrow, self.threshold_wide, self.channel_mask_narrow, self.channel_mask_wide, self.min_pulse_duration)

  @staticmethod
  def default_dwell():
    return esm_message_dwell_entry(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)

  @staticmethod
  def default_scan_dwell(entry_index, tag, freq, duration, fast_lock_profile):
    #TODO: chan mask
    duration_in_cycles = int(duration / FAST_CLOCK_PERIOD)
    return esm_message_dwell_entry(entry_index, tag, freq, duration_in_cycles, 0, fast_lock_profile, 0, 0, 0xFFFFFFFFFFFFFFFF, 0xFF, 0)

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
