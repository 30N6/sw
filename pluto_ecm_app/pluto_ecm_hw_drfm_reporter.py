import numpy as np

from pluto_ecm_hw_pkg import *
import pluto_ecm_hw_dwell


class pluto_ecm_hw_drfm_reporter:
  def __init__(self, logger):
    self.logger = logger
    self.next_msg_seq_num = 0

    self.logger.log(self.logger.LL_INFO, "[pluto_ecm_hw_drfm_reporter] init")

  def _process_common_header(self, data):
    assert (len(data) == DMA_TRANSFER_SIZE)
    unpacked_header = PACKED_ECM_REPORT_COMMON_HEADER.unpack(data[:PACKED_ECM_REPORT_COMMON_HEADER.size])

    magic_num   = unpacked_header[0]
    msg_seq_num = unpacked_header[1]
    msg_type    = unpacked_header[2]
    mod_id      = unpacked_header[3]

    assert (magic_num == ECM_REPORT_MAGIC_NUM)
    assert (msg_type in (ECM_REPORT_MESSAGE_TYPE_DRFM_CHANNEL_DATA, ECM_REPORT_MESSAGE_TYPE_DRFM_SUMMARY))
    assert (mod_id == ECM_MODULE_ID_DRFM)

    if msg_seq_num != self.next_msg_seq_num:
      self.logger.log(self.logger.LL_WARN, "PDW seq num gap: expected {}, received {}".format(self.next_msg_seq_num, msg_seq_num))
    self.next_msg_seq_num = (msg_seq_num + 1) & 0xFFFFFFFF

    return msg_type

  def _process_drfm_summary_message(self, data):
    unpacked_header = PACKED_DRFM_SUMMARY_REPORT_HEADER.unpack(data[:PACKED_DRFM_SUMMARY_REPORT_HEADER.size])

    report = {}
    report["msg_seq_num"]                 = unpacked_header[1]
    report["msg_type"]                    = unpacked_header[2]

    report["dwell_seq_num"]               = unpacked_header[4]

    report["channel_was_written"]         = unpacked_header[6]
    report["channel_was_read"]            = unpacked_header[5]

    report["report_delay_channel_write"]  = unpacked_header[7]
    report["report_delay_summary_write"]  = unpacked_header[8]
    report["report_delay_summary_start"]  = unpacked_header[9]

    return report

  def _process_drfm_channel_data_message(self, data):
    unpacked_header = PACKED_DRFM_CHANNEL_REPORT_HEADER.unpack(data[:PACKED_DRFM_CHANNEL_REPORT_HEADER.size])

    report = {}
    report["msg_seq_num"]         = unpacked_header[1]
    report["msg_type"]            = unpacked_header[2]
    report["dwell_seq_num"]       = unpacked_header[4]

    report["trigger_forced"]      = unpacked_header[5]
    report["channel_index_hw"]    = unpacked_header[7]
    report["channel_index"]       = pluto_ecm_hw_dwell.ecm_channel_index_hw_to_sw(unpacked_header[7])
    report["max_iq_bits"]         = unpacked_header[6]
    report["segment_seq_num"]     = unpacked_header[8]
    report["segment_timestamp"]   = (unpacked_header[9] << 32) | unpacked_header[10]
    report["segment_addr_first"]  = unpacked_header[12]
    report["segment_addr_last"]   = unpacked_header[11]
    report["slice_addr"]          = unpacked_header[14]
    report["slice_length"]        = unpacked_header[13]

    assert (report["slice_length"] <= ECM_DRFM_MAX_PACKET_IQ_SAMPLES_PER_REPORT)
    assert (report["slice_length"] > 0)

    # fast method
    report_data = np.frombuffer(data, dtype=np.int16)
    iq_data = report_data[(PACKED_DRFM_CHANNEL_REPORT_HEADER.size//2) : (PACKED_DRFM_CHANNEL_REPORT_HEADER.size//2 + 2 * report["slice_length"])]
    iq_data = iq_data.reshape((report["slice_length"], 2))
    iq_data = iq_data[:, -1::-1]

    # slow method - TODO: remove
    #iq_data = [[0, 0] for i in range(report["slice_length"])]
    #for i in range(report["slice_length"]):
    #  unpacked_word = PACKED_DRFM_IQ_WORD.unpack(data[(PACKED_DRFM_CHANNEL_REPORT_HEADER.size + PACKED_DRFM_IQ_WORD.size * i) :
    #                                                  (PACKED_DRFM_CHANNEL_REPORT_HEADER.size + PACKED_DRFM_IQ_WORD.size * (i + 1))])
    #  #TODO: verify IQ order
    #  iq_data[i][1] = unpacked_word[0]
    #  iq_data[i][0] = unpacked_word[1]


    #print("np={} p={}".format(iq_data_np[0:4], iq_data[0:4]))

    report["iq_data"] = iq_data

    return report

  def process_message(self, data):
    msg_type = self._process_common_header(data)

    if msg_type == ECM_REPORT_MESSAGE_TYPE_DRFM_SUMMARY:
      return self._process_drfm_summary_message(data)
    elif msg_type == ECM_REPORT_MESSAGE_TYPE_DRFM_CHANNEL_DATA:
      return self._process_drfm_channel_data_message(data)
    else:
      raise RuntimeError("invalid message")
