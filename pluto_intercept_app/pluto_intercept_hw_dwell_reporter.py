from pluto_intercept_hw_pkg import *

class pluto_intercept_hw_dwell_reporter:
  def __init__(self, logger):
    self.logger = logger
    self.next_msg_seq_num = 0

    self.partial_dwell_report = None
    self.partial_dwell_channel_data = []
    self.partial_dwell_channel_index = []

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

    report["dwell_seq_num"]         = unpacked_header[4]
    report["dwell_tag"]             = unpacked_header[5]
    report["dwell_frequency"]       = unpacked_header[6]
    report["dwell_window_duration"] = unpacked_header[7]

    report["window_seq_num"]        = unpacked_header[8]
    report["window_timestamp"]      = (unpacked_header[9] << 32) | unpacked_header[10]

    if self.partial_dwell_report is None:
      assert (len(self.partial_dwell_channel_data) == 0)
      assert (len(self.partial_dwell_channel_index) == 0)
      self.partial_dwell_report = report
    else:
      if (self.partial_dwell_report != report):
        print("[hw_dwell_reporter] mismatch: partial_dwell_report={}".format(self.partial_dwell_report))
        print("[hw_dwell_reporter] mismatch:               report={}".format(report))
        self.logger.log(self.logger.LL_WARN, "[hw_dwell_reporter] mismatch: partial_dwell_report={}".format(self.partial_dwell_report))
        self.logger.log(self.logger.LL_WARN, "[hw_dwell_reporter] mismatch:               report={}".format(report))
        self.logger.flush()
      assert (self.partial_dwell_report == report)

    trailer_bytes = PACKED_DWELL_STATS_HEADER.size - data.size
    num_reported_channels = trailer_bytes // PACKED_DWELL_STATS_CHANNEL_ENTRY.size

    for i in range(num_reported_channels):
      unpacked_channel_entry = PACKED_DWELL_STATS_CHANNEL_ENTRY.unpack(data[(PACKED_DWELL_STATS_HEADER.size + PACKED_DWELL_STATS_CHANNEL_ENTRY.size * i) :
                                                                            (PACKED_DWELL_STATS_HEADER.size + PACKED_DWELL_STATS_CHANNEL_ENTRY.size * (i + 1))])
      channel_index = unpacked_channel_entry[0]
      channel_accum = (unpacked_channel_entry[1] << 32) | unpacked_channel_entry[2]
      channel_max   = unpacked_channel_entry[3]

      assert(channel_index not in self.partial_dwell_channel_index)
      self.partial_dwell_channel_index.append(channel_index)
      self.partial_dwell_channel_data.append({"index": channel_index, "accum": channel_accum, "max": channel_max})

    if (len(self.partial_dwell_channel_data) == INTERCEPT_NUM_CHANNELS):
      report["channel_data"] = self.partial_dwell_channel_data
      self.partial_dwell_report = None
      self.partial_dwell_channel_data = []
      self.partial_dwell_channel_index = []
      return report
    else:
      return None

