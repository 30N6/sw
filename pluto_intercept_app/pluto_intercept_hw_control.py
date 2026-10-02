import struct
from pluto_intercept_hw_pkg import *

class intercept_dwell_control_entry:
  def __init__(self, enable, tag, frequency, duration):
    assert (enable    <= 1)
    assert (tag       <= 0xFFFF)
    assert (duration  <= 0xFFFF)
    assert (frequency <= 0xFFFFFFFF)

    self.fields                     = {}
    self.fields["enable"]           = enable
    self.fields["dwell_tag"]        = tag
    self.fields["dwell_frequency"]  = frequency
    self.fields["window_duration"]  = duration

  def __str__(self):
    return "[dwell_control_entry: fields={}]".format(self.fields)
  def __repr__(self):
    return self.__str__()

  def pack(self):
    return PACKED_INTERCEPT_CONFIG_DWELL_CONTROL.pack(self.fields["enable"], self.fields["dwell_tag"], self.fields["dwell_frequency"], self.fields["window_duration"])

class intercept_channel_control_entry:
  def __init__(self, enable, force_trigger, force_stream, tag, threshold_start, threshold_continue, coast_cycles, integration_cycles):
    assert (enable              <= 1)
    assert (force_trigger       <= 1)
    assert (force_stream        < INTERCEPT_NUM_STREAMS)
    assert (tag                 <= 0xFFFF)
    assert (threshold_start     <= 0xFFFFFFFF)
    assert (threshold_continue  <= 0xFFFFFFFF)
    assert (coast_cycles        <= 0x00FFFFFF)
    assert (integration_cycles  <= 0xFFFF)

    self.fields                       = {}
    self.fields["enable"]             = enable
    self.fields["force_trigger"]      = force_trigger
    self.fields["force_stream"]       = force_stream
    self.fields["stream_encoder_tag"] = tag
    self.fields["threshold_start"]    = threshold_start
    self.fields["threshold_continue"] = threshold_continue
    self.fields["coast_cycles"]       = coast_cycles
    self.fields["integration_cycles"] = integration_cycles

  def pack(self):
    packed_data = PACKED_INTERCEPT_CONFIG_CHANNEL_CONTROL.pack( self.fields["enable"],
                                                                self.fields["force_trigger"], self.fields["force_stream"],
                                                                self.fields["stream_encoder_tag"],
                                                                self.fields["threshold_start"], self.fields["threshold_continue"],
                                                                self.fields["coast_cycles"], self.fields["integration_cycles"])
    return packed_data

  def __str__(self):
    return "[channel_control_entry: fields={}]".format(self.fields)
  def __repr__(self):
    return self.__str__()

class intercept_stream_control_entry:
  def __init__(self, enable, tag):
    assert (enable              <= 1)
    assert (tag                 <= 0xFFFF)

    self.fields                       = {}
    self.fields["enable"]             = enable
    self.fields["stream_encoder_tag"] = tag

  def pack(self):
    packed_data = PACKED_INTERCEPT_CONFIG_CHANNEL_CONTROL.pack( self.fields["enable"],
                                                                self.fields["stream_encoder_tag"])
    return packed_data

  def __str__(self):
    return "[stream_control_entry: fields={}]".format(self.fields)
  def __repr__(self):
    return self.__str__()

class intercept_hardware_control:
  def __init__(self, config_writer):
    self.config_writer = config_writer

    self.current_dwell_entry      = None
    self.channel_entries_by_index = {}
    self.stream_entries_by_index  = {}

  def send_dwell_entry(self, dwell_entry):
    self.current_dwell_entry = dwell_entry
    return self.config_writer.send_module_data(INTERCEPT_MODULE_ID_DWELL_CONTROLLER, INTERCEPT_CONTROL_MESSAGE_TYPE_DWELL_CONTROLLER_CONFIG, dwell_entry.pack(), True)

  def send_channel_entry(self, channel_index, channel_entry):
    self.channel_entries_by_index[channel_index] = channel_entry
    return self.config_writer.send_module_data(INTERCEPT_MODULE_ID_STREAM_ENCODER, INTERCEPT_CONTROL_MESSAGE_TYPE_CHANNEL_CONFIG, channel_index, channel_entry.pack(), True)

  def send_stream_entry(self, stream_index, stream_entry):
    self.stream_entries_by_index[stream_index] = stream_entry
    return self.config_writer.send_module_data(INTERCEPT_MODULE_ID_STREAM_ENCODER, INTERCEPT_CONTROL_MESSAGE_TYPE_CHANNEL_CONFIG, stream_index, stream_entry.pack(), True)
