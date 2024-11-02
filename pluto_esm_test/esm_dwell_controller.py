import struct
import iio

PACKED_UINT8  = "B"
PACKED_UINT16 = "H"
PACKED_UINT32 = "I"
PACKED_UINT64 = "Q"

#TODO: esm_pkg
ESM_CONTROL_MAGIC_NUM                   = 0x45534D43
ESM_MODULE_ID_DWELL_CONTROLLER          = 0x01
ESM_CONTROL_MESSAGE_TYPE_DWELL_ENTRY    = 0x01
ESM_CONTROL_MESSAGE_TYPE_DWELL_PROGRAM  = 0x02

ESM_NUM_DWELL_ENTRIES       = 32
ESM_NUM_DWELL_INSTRUCTIONS  = 32
ESM_NUM_FAST_LOCK_PROFILES  = 8
ADC_CLOCK_PERIOD            = 1/61.44e6
FAST_CLOCK_PERIOD           = 1/(4*61.44e6)

class esm_message_dwell_entry:
  PACKED_ESM_MESSAGE_DWELL_ENTRY = struct.Struct("<" +
                                                  PACKED_UINT8 + "xxx" + "xxxx" +
                                                  PACKED_UINT16 + PACKED_UINT16 +
                                                  PACKED_UINT32 +
                                                  PACKED_UINT8 + PACKED_UINT8 + "xx" +
                                                  PACKED_UINT32 +
                                                  PACKED_UINT32 +
                                                  PACKED_UINT64 +
                                                  PACKED_UINT8 + "x" + PACKED_UINT16)

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
    return self.PACKED_ESM_MESSAGE_DWELL_ENTRY.pack(self.entry_index, self.tag, self.frequency, self.duration, self.gain, self.fast_lock_profile, self.threshold_narrow, self.threshold_wide, self.channel_mask_narrow, self.channel_mask_wide, self.min_pulse_duration)

class esm_dwell_instruction:
  PACKED_DWELL_INSTRUCTION = struct.Struct("<" + PACKED_UINT8 + PACKED_UINT8 + PACKED_UINT8 + PACKED_UINT8)

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
    return self.PACKED_DWELL_INSTRUCTION.pack(command_byte, self.repeat_count, self.entry_index, self.next_instruction_index)

class esm_message_dwell_program:
  PACKED_DWELL_PROGRAM = struct.Struct("<" + PACKED_UINT8 + PACKED_UINT8 + "xx" + PACKED_UINT32 + PACKED_UINT64)

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
    packed_data = self.PACKED_DWELL_PROGRAM.pack(self.enable_program, self.enable_delayed_start, self.global_counter_init, self.delayed_start_time)
    for i in range(len(self.instructions)):
      packed_data += self.instructions[i].pack()
    return packed_data

class esm_dwell_controller:
  def __init__(self, config_writer):
    self.config_writer = config_writer
    self.dwell_tag = 0
    self.dwells_by_tag = {}
    self.current_dwell_program = []
    #TODO: logger

  #TODO: load from file

  def send_default_dwell_entries(self):
    for i in range(4): #range(ESM_NUM_DWELL_ENTRIES):
      power_threshold = 30000
      pd_threshold = 50
      dwell_entry = esm_message_dwell_entry(i, self.dwell_tag, i * 1000, int(0.5 / FAST_CLOCK_PERIOD), 0, i % ESM_NUM_FAST_LOCK_PROFILES, power_threshold, power_threshold, 0xFFFFFFFFFFFFFFFF, 0xFF, pd_threshold)
      self.dwell_tag += 1
      self._send_dwell_entry(dwell_entry)

  def send_default_dwell_program(self):
    dwell_instructions = []
    for i in range(ESM_NUM_DWELL_INSTRUCTIONS):
      dwell_instructions.append(esm_dwell_instruction(i < 5, 0, 0, 1, 1, 1, 0, i, (i + 1) % 4))
      #dwell_instructions.append(esm_dwell_instruction(i < 5, 0, 0, 1, 1, 1, 0, i, (i + 1) % ESM_NUM_DWELL_INSTRUCTIONS ))
    dwell_program = esm_message_dwell_program(1, 0, 100, 200, dwell_instructions)
    self._send_dwell_program(dwell_program)

  def _send_dwell_entry(self, dwell_entry):
    self.config_writer.send_module_data(ESM_MODULE_ID_DWELL_CONTROLLER, ESM_CONTROL_MESSAGE_TYPE_DWELL_ENTRY, dwell_entry.pack())
    self.dwells_by_tag[dwell_entry.tag] = dwell_entry

  def _send_dwell_program(self, dwell_program):
    self.config_writer.send_module_data(ESM_MODULE_ID_DWELL_CONTROLLER, ESM_CONTROL_MESSAGE_TYPE_DWELL_PROGRAM, dwell_program.pack())
    self.current_dwell_program = dwell_program