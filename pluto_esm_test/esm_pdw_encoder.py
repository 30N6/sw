import struct
from esm_pkg import *

class esm_pdw_encoder:
  PACKED_PDW_PULSE_REPORT_HEADER = struct.Struct("<" + PACKED_UINT32 + PACKED_UINT32 + "xx" + PACKED_UINT8 + PACKED_UINT8 +
                                                       PACKED_UINT32 +
                                                       PACKED_UINT32 +
                                                       PACKED_UINT32 +
                                                       PACKED_UINT32 +
                                                       PACKED_UINT32 + PACKED_UINT32 +
                                                       PACKED_UINT32 +
                                                       PACKED_UINT32 +
                                                       PACKED_UINT32 + PACKED_UINT32 +
                                                       "xx" + PACKED_UINT8 + PACKED_UINT8)

  PACKED_PDW_SUMMARY_REPORT = struct.Struct("<" + PACKED_UINT32 + PACKED_UINT32 + "xx" + PACKED_UINT8 + PACKED_UINT8 +
                                                  PACKED_UINT32 +
                                                  PACKED_UINT32 + PACKED_UINT32 +
                                                  PACKED_UINT32 +
                                                  PACKED_UINT32 +
                                                  PACKED_UINT32)

  PACKED_PDW_SAMPLE_WORD = struct.Struct("<" + PACKED_INT16 + PACKED_INT16)

  NUM_PULSE_TRAILER_WORDS = (TRANSFER_SIZE - PACKED_PDW_PULSE_REPORT_HEADER.size) // 4

  def __init__(self, logger):
    self.next_msg_seq_num = 0

    #TODO: logging
    pass

  def _process_common_header(self, data):
    assert (len(data) == TRANSFER_SIZE)
    #TODO: logging

    unpacked_header = PACKED_ESM_REPORT_COMMON_HEADER.unpack(data[:PACKED_ESM_REPORT_COMMON_HEADER.size])
    magic_num   = unpacked_header[0]
    msg_seq_num = unpacked_header[1]
    msg_type    = unpacked_header[2]
    mod_id      = unpacked_header[3]

    assert (magic_num == ESM_REPORT_MAGIC_NUM)
    assert (msg_type in (ESM_REPORT_MESSAGE_TYPE_PDW_PULSE, ESM_REPORT_MESSAGE_TYPE_PDW_SUMMARY))
    assert (mod_id in (ESM_MODULE_ID_PDW_NARROW, ESM_MODULE_ID_PDW_WIDE))

    if msg_seq_num != self.next_msg_seq_num:
      #TODO: logging
      print("PDW seq num gap: expected {}, received {}".format(self.next_msg_seq_num, msg_seq_num))
    self.next_msg_seq_num = (msg_seq_num + 1) & 0xFFFFFFFF

    return msg_type

  def _process_pdw_summary_message(self, data):
    unpacked_header = self.PACKED_PDW_SUMMARY_REPORT.unpack(data[:self.PACKED_PDW_SUMMARY_REPORT.size])
    dwell_seq_num           = unpacked_header[4]
    dwell_start_time        = (unpacked_header[5] << 32) | unpacked_header[6]
    dwell_duration          = unpacked_header[7]
    dwell_pulse_total_count = unpacked_header[8]
    dwell_pulse_drop_count  = unpacked_header[9]

    print("pdw_summary: dwell_seq={} ts_start={} duration={} pulse_count={} drop_count={}".format(dwell_seq_num, dwell_start_time, dwell_duration, dwell_pulse_total_count, dwell_pulse_drop_count))

  def _process_pdw_pulse_message(self, data):
    unpacked_header = self.PACKED_PDW_PULSE_REPORT_HEADER.unpack(data[:self.PACKED_PDW_PULSE_REPORT_HEADER.size])
    dwell_seq_num     = unpacked_header[4]
    pulse_seq_num     = unpacked_header[5]
    pulse_channel     = unpacked_header[6]
    pulse_threshold   = unpacked_header[7]
    pulse_power_accum = (unpacked_header[8] << 32) | unpacked_header[9]
    pulse_duration    = unpacked_header[10]
    pulse_frequency   = unpacked_header[11]
    pulse_start_time  = (unpacked_header[12] << 32) | unpacked_header[13]
    pulse_buf_index   = unpacked_header[14]
    pulse_buf_valid   = unpacked_header[15]

    pulse_samples = []
    for i in range(self.NUM_PULSE_TRAILER_WORDS):
      unpacked_sample = self.PACKED_PDW_SAMPLE_WORD.unpack(data[(self.PACKED_PDW_PULSE_REPORT_HEADER.size + self.PACKED_PDW_SAMPLE_WORD.size * i) :
                                                                (self.PACKED_PDW_PULSE_REPORT_HEADER.size + self.PACKED_PDW_SAMPLE_WORD.size * (i + 1))])
      pulse_samples.append(unpacked_sample)

    print("pdw_pulse: dwell_seq={} pulse_ch={} seq={} duration={} power_accum={} ts_start={} buf_valid={} buf_index={}".format(dwell_seq_num, pulse_channel, pulse_seq_num, pulse_duration, pulse_power_accum, pulse_start_time, pulse_buf_valid, pulse_buf_index))
    if pulse_buf_valid:
      print("   trailer: {}".format(pulse_samples))

  def process_message(self, data):
    msg_type = self._process_common_header(data)

    if (msg_type == ESM_REPORT_MESSAGE_TYPE_PDW_SUMMARY):
      self._process_pdw_summary_message(data)
    elif (msg_type == ESM_REPORT_MESSAGE_TYPE_PDW_PULSE):
      self._process_pdw_pulse_message(data)
    else:
      raise RuntimeError("unknown message type {}".format(msg_type))
