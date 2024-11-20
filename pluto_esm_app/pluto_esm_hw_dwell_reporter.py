from pluto_esm_hw_pkg import *

class pluto_esm_hw_dwell_reporter:
  def __init__(self, logger):
    self.logger = logger
    self.next_msg_seq_num = 0

    self.partial_dwell_report = None
    self.partial_dwell_channels = []

    self.logger.log(self.logger.LL_INFO, "[pluto_esm_hw_dwell_reporter] init")

  def _process_common_header(self, data):
    assert (len(data) == TRANSFER_SIZE)
    unpacked_header = PACKED_ESM_REPORT_COMMON_HEADER.unpack(data[:PACKED_ESM_REPORT_COMMON_HEADER.size])

    magic_num   = unpacked_header[0]
    msg_seq_num = unpacked_header[1]
    msg_type    = unpacked_header[2]
    mod_id      = unpacked_header[3]

    assert (magic_num == ESM_REPORT_MAGIC_NUM)
    assert (msg_type == ESM_REPORT_MESSAGE_TYPE_DWELL_STATS)
    assert (mod_id in (ESM_MODULE_ID_DWELL_STATS_NARROW, ESM_MODULE_ID_DWELL_STATS_WIDE))

    if msg_seq_num != self.next_msg_seq_num:
      self.logger.log(self.logger.LL_WARN, "Dwell stats seq num gap: expected {}, received {}".format(self.next_msg_seq_num, msg_seq_num))
    self.next_msg_seq_num = (msg_seq_num + 1) & 0xFFFFFFFF

  def process_message(self, data):
    self._process_common_header(data)
    #TODO: is this dwell header scheme reasonable? seems inefficient

    unpacked_header = PACKED_DWELL_STATS_HEADER.unpack(data[:PACKED_DWELL_STATS_HEADER.size])

    report = {}
    report["dwell_seq_num"]           = unpacked_header[4]
    report["frequency"]               = unpacked_header[5]
    report["tag"]                     = unpacked_header[6]
    report["duration_requested"]      = unpacked_header[7]
    report["num_channels"]            = unpacked_header[9]
    report["fast_lock_profile"]       = unpacked_header[10]
    report["gain"]                    = unpacked_header[11]
    report["threshold_shift_wide"]    = unpacked_header[12]
    report["threshold_shift_narrow"]  = unpacked_header[13]
    report["dwell_duration"]          = unpacked_header[14]
    report["num_samples"]             = unpacked_header[15]
    report["ts_dwell_start"]          = (unpacked_header[16] << 32) | unpacked_header[17]
    report["ts_dwell_end"]            = (unpacked_header[18] << 32) | unpacked_header[19]

    report_starting_channel = unpacked_header[8]

    if self.partial_dwell_report is None:
      assert (len(self.partial_dwell_channels) == 0)
      self.partial_dwell_report = report
    else:
      assert (self.partial_dwell_report == report)

    computed_duration = report["ts_dwell_end"] - report["ts_dwell_start"]
    assert (report["dwell_duration"] == computed_duration)  #TODO: remove redundant field
    assert (report["num_channels"] in (ESM_NUM_CHANNELS_WIDE, ESM_NUM_CHANNELS_NARROW))

    num_reported_channels = min(NUM_DWELL_STATS_TRAILER_BYTES // PACKED_DWELL_STATS_CHANNEL_ENTRY.size, report["num_channels"] - report_starting_channel)
    for i in range(num_reported_channels):
      unpacked_channel_entry = PACKED_DWELL_STATS_CHANNEL_ENTRY.unpack(data[(PACKED_DWELL_STATS_HEADER.size + PACKED_DWELL_STATS_CHANNEL_ENTRY.size * i) :
                                                                            (PACKED_DWELL_STATS_HEADER.size + PACKED_DWELL_STATS_CHANNEL_ENTRY.size * (i + 1))])
      channel_index = unpacked_channel_entry[0]
      channel_accum = (unpacked_channel_entry[1] << 32) | unpacked_channel_entry[2]
      channel_max   = unpacked_channel_entry[3]
      assert ((report_starting_channel + i) == channel_index)
      self.partial_dwell_channels.append({"index": channel_index, "accum": channel_accum, "max": channel_max})

    if (report["num_channels"] == len(self.partial_dwell_channels)):
      report["channel_data"] = self.partial_dwell_channels
      self.partial_dwell_report = None
      self.partial_dwell_channels = []

      #print("dwell reporter: freq={} channels={}".format(report["frequency"], report["channel_data"]))
      #print("dwell reporter: freq={}".format(report["frequency"]))

      return report
    else:
      return None
