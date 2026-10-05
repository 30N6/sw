from pluto_intercept_hw_pkg import *
import numpy as np

class pluto_intercept_hw_dwell_reporter:
  def __init__(self, logger):
    self.logger                       = logger
    self.next_msg_seq_num             = 0
    self.partial_dwell_report         = None
    self.partial_dwell_channel_index  = []
    self.channel_accum                = np.empty(INTERCEPT_NUM_CHANNELS)
    self.channel_max                  = np.empty(INTERCEPT_NUM_CHANNELS)

    self.logger.log(self.logger.LL_INFO, "[pluto_intercept_hw_dwell_reporter] init")

  def _process_common_header(self, data):
    unpacked_header = PACKED_INTERCEPT_REPORT_COMMON_HEADER.unpack(data[:PACKED_INTERCEPT_REPORT_COMMON_HEADER.size])

    magic_num   = unpacked_header[0]
    msg_seq_num = unpacked_header[1]
    msg_type    = unpacked_header[2]
    mod_id      = unpacked_header[3]

    assert (magic_num == INTERCEPT_REPORT_MAGIC_NUM)
    assert (msg_type == INTERCEPT_REPORT_MESSAGE_TYPE_DWELL_STATS)
    assert (mod_id == INTERCEPT_MODULE_ID_DWELL_STATS)

    if msg_seq_num != self.next_msg_seq_num:
      self.logger.log(self.logger.LL_WARN, "Dwell stats seq num gap: expected {}, received {}".format(self.next_msg_seq_num, msg_seq_num))
    self.next_msg_seq_num = (msg_seq_num + 1) & 0xFFFFFFFF

  def process_message(self, data):
    self._process_common_header(data)

    unpacked_header = PACKED_DWELL_STATS_HEADER.unpack(data[:PACKED_DWELL_STATS_HEADER.size])

    report = {}

    report["msg_seq_num"]           = unpacked_header[1]
    report["msg_type"]              = unpacked_header[2]

    self.logger.log(self.logger.LL_DEBUG, "[hw_dwell_reporter] len={} seq={}".format(len(data), report["msg_seq_num"]))

    report["dwell_seq_num"]         = unpacked_header[4]
    report["dwell_frequency"]       = unpacked_header[5]
    report["dwell_tag"]             = unpacked_header[7]
    report["dwell_window_duration"] = unpacked_header[6]

    report["window_seq_num"]        = unpacked_header[8]
    report["window_timestamp"]      = (unpacked_header[9] << 32) | unpacked_header[10]

    if self.partial_dwell_report is None:
      assert (len(self.partial_dwell_channel_index) == 0)
      self.partial_dwell_report = report
    else:
      if (self.partial_dwell_report["dwell_seq_num"] != report["dwell_seq_num"]) or (self.partial_dwell_report["window_seq_num"] != report["window_seq_num"]):
        print("[hw_dwell_reporter] mismatch: partial_dwell_report={}".format(self.partial_dwell_report))
        print("[hw_dwell_reporter] mismatch:               report={}".format(report))
        self.logger.log(self.logger.LL_WARN, "[hw_dwell_reporter] mismatch: partial_dwell_report={}".format(self.partial_dwell_report))
        self.logger.log(self.logger.LL_WARN, "[hw_dwell_reporter] mismatch:               report={}".format(report))
        self.logger.flush()

    trailer_bytes = len(data) - PACKED_DWELL_STATS_HEADER.size
    num_reported_channels = trailer_bytes // PACKED_DWELL_STATS_CHANNEL_ENTRY.size

    for i in range(num_reported_channels):
      unpacked_channel_entry = PACKED_DWELL_STATS_CHANNEL_ENTRY.unpack(data[(PACKED_DWELL_STATS_HEADER.size + PACKED_DWELL_STATS_CHANNEL_ENTRY.size * i) :
                                                                            (PACKED_DWELL_STATS_HEADER.size + PACKED_DWELL_STATS_CHANNEL_ENTRY.size * (i + 1))])
      if not unpacked_channel_entry[0]: #channel_valid
        break

      channel_index = unpacked_channel_entry[1]

      self.channel_accum[channel_index] = (unpacked_channel_entry[2] << 32) | unpacked_channel_entry[3]
      self.channel_max[channel_index]   = unpacked_channel_entry[4]

      assert(channel_index not in self.partial_dwell_channel_index)
      self.partial_dwell_channel_index.append(channel_index)

    if (len(self.partial_dwell_channel_index) == INTERCEPT_NUM_CHANNELS):
      self.partial_dwell_report = None
      self.partial_dwell_channel_index = []
      #TODO: copy needed?
      report["channel_accum"] = self.channel_accum.copy()
      report["channel_max"] = self.channel_max.copy()
      return report
    else:
      return None
