from pluto_esm_hw_pkg import *

class pluto_esm_hw_pdw_reporter:
  def __init__(self, logger):
    self.logger = logger
    self.next_msg_seq_num = 0

    self.logger.log(self.logger.LL_INFO, "[pluto_esm_hw_pdw_reporter] init")

  def _process_common_header(self, data):
    assert (len(data) == TRANSFER_SIZE)
    unpacked_header = PACKED_ESM_REPORT_COMMON_HEADER.unpack(data[:PACKED_ESM_REPORT_COMMON_HEADER.size])

    magic_num   = unpacked_header[0]
    msg_seq_num = unpacked_header[1]
    msg_type    = unpacked_header[2]
    mod_id      = unpacked_header[3]

    assert (magic_num == ESM_REPORT_MAGIC_NUM)
    assert (msg_type in (ESM_REPORT_MESSAGE_TYPE_PDW_PULSE, ESM_REPORT_MESSAGE_TYPE_PDW_SUMMARY))
    assert (mod_id in (ESM_MODULE_ID_PDW_NARROW, ESM_MODULE_ID_PDW_WIDE))

    if msg_seq_num != self.next_msg_seq_num:
      self.logger.log(self.logger.LL_WARN, "PDW seq num gap: expected {}, received {}".format(self.next_msg_seq_num, msg_seq_num))
    self.next_msg_seq_num = (msg_seq_num + 1) & 0xFFFFFFFF

    return msg_type

  def _process_pdw_summary_message(self, data):
    unpacked_header = PACKED_PDW_SUMMARY_REPORT_HEADER.unpack(data[:PACKED_PDW_SUMMARY_REPORT_HEADER.size])

    report = {}
    report["msg_seq_num"]                 = unpacked_header[1]
    report["msg_type"]                    = unpacked_header[2]
    report["dwell_seq_num"]               = unpacked_header[4]
    report["dwell_start_time"]            = (unpacked_header[5] << 32) | unpacked_header[6]
    report["dwell_duration"]              = unpacked_header[7]
    report["dwell_pulse_total_count"]     = unpacked_header[8]
    report["dwell_pulse_drop_count"]      = unpacked_header[9]
    report["ack_delay_report"]            = unpacked_header[10]
    report["ack_delay_sample_processor"]  = unpacked_header[11]

    return report

  def _process_pdw_pulse_message(self, data):
    unpacked_header = PACKED_PDW_PULSE_REPORT_HEADER.unpack(data[:PACKED_PDW_PULSE_REPORT_HEADER.size])

    report = {}
    report["msg_seq_num"]             = unpacked_header[1]
    report["msg_type"]                = unpacked_header[2]
    report["dwell_seq_num"]           = unpacked_header[4]
    report["pulse_seq_num"]           = unpacked_header[5]
    report["pulse_channel"]           = unpacked_header[6]
    report["pulse_threshold"]         = unpacked_header[7]
    report["pulse_power_accum"]       = (unpacked_header[8] << 32) | unpacked_header[9]
    report["pulse_duration"]          = unpacked_header[10]
    report["pulse_frequency"]         = unpacked_header[11]
    report["pulse_start_time"]        = (unpacked_header[12] << 32) | unpacked_header[13]
    report["buffered_frame_valid"]    = unpacked_header[14]
    report["buffered_frame_index"]    = unpacked_header[15]

    if report["buffered_frame_valid"]:
      pulse_iq_data = [[0, 0] for i in range(NUM_PDW_PULSE_TRAILER_WORDS)]

      for i in range(NUM_PDW_PULSE_TRAILER_WORDS):
        unpacked_word = PACKED_PDW_PULSE_IQ_WORD.unpack(data[(PACKED_PDW_PULSE_REPORT_HEADER.size + PACKED_PDW_PULSE_IQ_WORD.size * i) :
                                                             (PACKED_PDW_PULSE_REPORT_HEADER.size + PACKED_PDW_PULSE_IQ_WORD.size * (i + 1))])

        #TODO: verify IQ order
        pulse_iq_data[i][1] = unpacked_word[0]
        pulse_iq_data[i][0] = unpacked_word[1]

      report["buffered_frame_data"] = pulse_iq_data

    return report

  def process_message(self, data):
    msg_type = self._process_common_header(data)

    if msg_type == ESM_REPORT_MESSAGE_TYPE_PDW_SUMMARY:
      return self._process_pdw_summary_message(data)
    elif msg_type == ESM_REPORT_MESSAGE_TYPE_PDW_PULSE:
      return self._process_pdw_pulse_message(data)
    else:
      raise RuntimeError("invalid message")
