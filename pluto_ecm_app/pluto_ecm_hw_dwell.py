import struct
from pluto_ecm_hw_pkg import *

#TODO
#def populate_dwell_entry(config, entry_index, center_freq, dwell_time, fast_lock_profile):
#  channel_spacing_MHz       = (ADC_CLOCK_FREQUENCY / ECM_NUM_CHANNELS) / 1e6
#  channel_sampling_freq_Mhz = channel_spacing_MHz * CHANNELIZER_OVERSAMPLING
#  channel_sampling_time_us  = 1 / channel_sampling_freq_Mhz
#
#  for i in range(ESM_NUM_CHANNELS_NARROW):
#    if (channel_mask_initial & (1 << i)) == 0:
#      continue
#    channel_freq = center_freq + (i - center_index)
#    for emitter in config["emitter_config"]["pulsed_emitters"]:
#      if (channel_freq >= emitter["freq_range"][0]) and (channel_freq <= emitter["freq_range"][1]):
#        channel_mask_final  = channel_mask_final | (1 << i)
#        min_threshold_dB    = min(min_threshold_dB, emitter["threshold_dB"])
#        PW_range[0]         = min(PW_range[0], emitter["PW_range"][0])
#        PW_range[1]         = max(PW_range[1], emitter["PW_range"][1])
#
#  min_threshold_linear = 10 ** (min_threshold_dB / 10)
#  threshold_shift = 0
#  while ((1 << threshold_shift) < min_threshold_linear):
#    threshold_shift += 1
#  assert (threshold_shift < 31)
#
#  duration_in_cycles = int(dwell_time / FAST_CLOCK_PERIOD)
#  min_pd = int((0.5 * PW_range[0]) // channel_sampling_time_us)
#
#  return ecm_dwell_entry(entry_index, entry_index, center_freq, duration_in_cycles, 0, fast_lock_profile, threshold_shift, 31, channel_mask_final, 0xFF, min_pd)


class ecm_dwell_program_entry:
  def __init__(self, enable, initial_dwell_index, global_counter_init, tag):
    assert (enable <= 1)
    assert (initial_dwell_index < ECM_NUM_DWELL_ENTRIES)
    assert (global_counter_init <= 0xFFFF)

    self.fields                         = {}
    self.fields["enable"]               = enable
    self.fields["initial_dwell_index"]  = initial_dwell_index
    self.fields["global_counter_init"]  = global_counter_init
    self.fields["tag"]                  = tag

  def pack(self):
    return PACKED_ECM_DWELL_PROGRAM_ENTRY.pack(self.fields["enable"], self.fields["initial_dwell_index"], self.fields["global_counter_init"], self.fields["tag"])

  def __str__(self):
    return "[dwell_program: fields={}]".format(self.fields)
  def __repr__(self):
    return self.__str__()

class ecm_dwell_entry:
  def __init__(self, valid, next_index, fast_lock_profile, tag, freq, duration_meas, duration_max, min_trigger_duration):
    assert (valid <= 1)
    assert (next_index < ECM_NUM_DWELL_ENTRIES)
    assert (fast_lock_profile < ECM_NUM_FAST_LOCK_PROFILES)
    assert (tag <= 0xFFFF)
    assert (freq <= 0xFFFF)
    assert (duration_meas <= 0x0FFFFFFF)
    assert (duration_max <= 0x0FFFFFFF)

    self.fields                           = {}
    self.fields["valid"]                  = valid
    self.fields["global_counter_check"]   = 1
    self.fields["global_counter_dec"]     = 1
    self.fields["skip_pll_prelock_wait"]  = 0
    self.fields["skip_pll_lock_check"]    = 0
    self.fields["skip_pll_postlock_wait"] = 0
    self.fields["repeat_count"]           = 0
    self.fields["fast_lock_profile"]      = fast_lock_profile
    self.fields["next_dwell_index"]       = next_index
    self.fields["pll_pre_lock_delay"]     = 1024
    self.fields["pll_post_lock_delay"]    = 2048
    self.fields["tag"]                    = tag
    self.fields["frequency"]              = freq
    self.fields["measurement_duration"]   = duration_meas
    self.fields["total_duration_max"]     = duration_max
    self.fields["min_trigger_duration"]   = min_trigger_duration

  def __str__(self):
    return "[dwell_entry: fields={}]".format(self.fields)
  def __repr__(self):
    return self.__str__()

  def pack(self):
    flags = (self.fields["skip_pll_postlock_wait"]  << 5) | \
            (self.fields["skip_pll_lock_check"]     << 4) | \
            (self.fields["skip_pll_prelock_wait"]   << 3) | \
            (self.fields["global_counter_dec"]      << 2) | \
            (self.fields["global_counter_check"]    << 1) | \
            (self.fields["valid"]                   << 0)

    return PACKED_ECM_DWELL_ENTRY.pack(flags, self.fields["repeat_count"], self.fields["fast_lock_profile"], self.fields["next_dwell_index"],
                                       self.fields["pll_pre_lock_delay"], self.fields["pll_post_lock_delay"],
                                       self.fields["tag"], self.fields["frequency"],
                                       self.fields["measurement_duration"],
                                       self.fields["total_duration_max"],
                                       self.fields["min_trigger_duration"])

  #@staticmethod
  #def default_dwell():
  #  return ecm_dwell_entry(0, 0, 0, 0, 0, 0, 0)
  #
  #TODO: remove?
  #@staticmethod
  #def default_scan_dwell(entry_index, tag, freq, duration, fast_lock_profile):
  #  duration_in_cycles = int(duration / FAST_CLOCK_PERIOD)
  #  min_pd = 1
  #  return ecm_dwell_entry(entry_index, tag, freq, duration_in_cycles, 0, fast_lock_profile, 7, 6, 0x0FFFFFFFFFFFFFF0, 0xFF, min_pd)
  #
  #@staticmethod
  #def from_dict(d):
  #  return ecm_dwell_entry(d["valid"], d["next_index"], )


def ecm_channel_index_hw_to_sw(hw_index):
  return (hw_index - ECM_NUM_CHANNELS//2) % ECM_NUM_CHANNELS
def ecm_channel_index_sw_to_hw(sw_index):
  return (sw_index + ECM_NUM_CHANNELS//2) % ECM_NUM_CHANNELS

class ecm_channel_control_entry:
  def __init__(self, enable, trigger_mode, trigger_duration_max_minus_one, trigger_threshold, trigger_hyst_shift, drfm_gain, recording_addr, program_entries):
    assert (enable <= 1)
    assert (trigger_mode <= ECM_CHANNEL_TRIGGER_MODE_THRESHOLD_TRIGGER)
    assert (trigger_duration_max_minus_one <= 0x0FFF)
    assert (trigger_threshold <= 0xFFFFFFFF)
    assert (trigger_hyst_shift <= (2**ECM_DRFM_SEGMENT_HYST_SHIFT_WIDTH - 1))
    assert (drfm_gain <= 1)
    assert (recording_addr <= 0x7FFF)
    assert (len(program_entries) == ECM_NUM_CHANNEL_TX_PROGRAM_ENTRIES)

    self.fields                                   = {}
    self.fields["enable"]                         = enable
    self.fields["trigger_mode"]                   = trigger_mode
    self.fields["trigger_duration_max_minus_one"] = trigger_duration_max_minus_one
    self.fields["trigger_threshold"]              = trigger_threshold
    self.fields["trigger_hyst_shift"]             = trigger_hyst_shift
    self.fields["drfm_gain"]                      = drfm_gain
    self.fields["recording_addr"]                 = recording_addr
    self.fields["program_entries"]                = program_entries

  def pack(self):
    packed_data = PACKED_ECM_CHANNEL_CONTROL_ENTRY_HEADER.pack(self.fields["enable"], self.fields["trigger_mode"], self.fields["trigger_duration_max_minus_one"],
                                                               self.fields["trigger_threshold"],
                                                               self.fields["trigger_hyst_shift"], self.fields["drfm_gain"], self.fields["recording_addr"])
    for i in range(ECM_NUM_CHANNEL_TX_PROGRAM_ENTRIES):
      packed_data += self.fields["program_entries"][i].pack()
    return packed_data

  def __str__(self):
    return "[channel_entry: fields={}]".format(self.fields)
  def __repr__(self):
    return self.__str__()

  @staticmethod
  def channel_entry_trigger_none(channel_index_sw):
    enable = (ECM_CHANNEL_MASK & (1 << channel_index_sw)) != 0
    program_entries = [ecm_channel_tx_program_entry(0, 0, 0, 0, 0) for i in range(ECM_NUM_CHANNEL_TX_PROGRAM_ENTRIES)]
    return ecm_channel_control_entry(enable, ECM_CHANNEL_TRIGGER_MODE_NONE, 0, 0xFFFFFFFF, 1, 0, 0, program_entries)

  @staticmethod
  def channel_entry_trigger_forced(channel_index_sw):
    enable = (ECM_CHANNEL_MASK & (1 << channel_index_sw)) != 0
    program_entries = [ecm_channel_tx_program_entry(0, 0, 0, 0, 0) for i in range(ECM_NUM_CHANNEL_TX_PROGRAM_ENTRIES)]

    recording_length = (ECM_DRFM_MEM_DEPTH // ECM_NUM_CHANNELS_ACTIVE)
    recording_addr = recording_length * ECM_ACTIVE_CHANNEL_DRFM_SEGMENT_MAP[channel_index_sw]
    return ecm_channel_control_entry(enable, ECM_CHANNEL_TRIGGER_MODE_FORCE_TRIGGER, recording_length - 1, 0xFFFFFFFF, 1, 0, recording_addr, program_entries)

  @staticmethod
  def channel_entry_trigger_threshold_listen_only(channel_index_sw, threshold, hyst_shift):
    enable = (ECM_CHANNEL_MASK & (1 << channel_index_sw)) != 0
    program_entries = [ecm_channel_tx_program_entry(0, 0, 0, 0, 0) for i in range(ECM_NUM_CHANNEL_TX_PROGRAM_ENTRIES)]

    recording_length = (ECM_DRFM_MEM_DEPTH // ECM_NUM_CHANNELS_ACTIVE)
    recording_addr = recording_length * ECM_ACTIVE_CHANNEL_DRFM_SEGMENT_MAP[channel_index_sw]
    return ecm_channel_control_entry(enable, ECM_CHANNEL_TRIGGER_MODE_THRESHOLD_TRIGGER, recording_length - 1, threshold, hyst_shift, 0, recording_addr, program_entries)


class ecm_channel_tx_program_entry:
  def __init__(self, valid, trigger_immediate_after_min, tx_instruction_index, duration_gate_min_minus_one, duration_gate_max_minus_one):
    assert (valid <= 1)
    assert (trigger_immediate_after_min <= 1)
    assert (tx_instruction_index < ECM_NUM_TX_INSTRUCTIONS)
    assert (duration_gate_min_minus_one <= 0x0FFF)
    assert (duration_gate_max_minus_one <= 0x0FFF)

    self.fields                                 = {}
    self.fields["valid"]                        = valid
    self.fields["trigger_immediate_after_min"]  = trigger_immediate_after_min
    self.fields["tx_instruction_index"]         = tx_instruction_index
    self.fields["duration_gate_min_minus_one"]  = duration_gate_min_minus_one
    self.fields["duration_gate_max_minus_one"]  = duration_gate_max_minus_one

  def pack(self):
    return PACKED_ECM_CHANNEL_TX_PROGRAM_ENTRY.pack(self.fields["valid"], self.fields["trigger_immediate_after_min"], self.fields["tx_instruction_index"],
                                                    self.fields["duration_gate_min_minus_one"], self.fields["duration_gate_max_minus_one"])

  def __str__(self):
    return "[tx_program_entry: fields={}]".format(self.fields)
  def __repr__(self):
    return self.__str__()


class ecm_dwell_controller:
  def __init__(self, config_writer):
    self.config_writer = config_writer

    self.current_dwell_program    = None
    self.dwells_by_index          = {}
    self.dwells_by_tag            = {}
    self.channel_entries_by_index = {}

  def send_dwell_program(self, dwell_program):
    self.current_dwell_program = dwell_program
    return self.config_writer.send_module_data(ECM_MODULE_ID_DWELL_CONTROLLER, ECM_CONTROL_MESSAGE_TYPE_DWELL_PROGRAM, 0, dwell_program.pack(), True)

  def send_dwell_entry(self, dwell_index, dwell_entry):
    self.dwells_by_index[dwell_index] = dwell_entry
    self.dwells_by_tag[dwell_entry.fields["tag"]] = {"index": dwell_index, "entry": dwell_entry}
    return self.config_writer.send_module_data(ECM_MODULE_ID_DWELL_CONTROLLER, ECM_CONTROL_MESSAGE_TYPE_DWELL_ENTRY, dwell_index, dwell_entry.pack(), True)

  def send_channel_entry(self, dwell_index, channel_index_sw, channel_entry):
    full_channel_index = dwell_index * ECM_NUM_CHANNELS + ecm_channel_index_sw_to_hw(channel_index_sw)

    self.channel_entries_by_index[full_channel_index] = channel_entry
    return self.config_writer.send_module_data(ECM_MODULE_ID_DWELL_CONTROLLER, ECM_CONTROL_MESSAGE_TYPE_DWELL_CHANNEL_CONTROL, full_channel_index, channel_entry.pack(), True)
