import struct
from esm_pkg import *

class esm_dwell_stats:
  PACKED_HEADER = struct.Struct("<" + PACKED_UINT32 + PACKED_UINT32 + "xx" + PACKED_UINT8 + PACKED_UINT8 +
                                      PACKED_UINT32 +
                                      PACKED_UINT16 + PACKED_UINT16 +
                                      PACKED_UINT32 +
                                      PACKED_UINT8 + PACKED_UINT8 + PACKED_UINT8 + PACKED_UINT8 +
                                      PACKED_UINT32 +
                                      PACKED_UINT32 +
                                      "xxxxxxxx" + "xxxx" +
                                      PACKED_UINT32 +
                                      PACKED_UINT32 +
                                      PACKED_UINT32 + PACKED_UINT32 +
                                      PACKED_UINT32 + PACKED_UINT32)

  PACKED_CHANNEL_ENTRY = struct.Struct("<" + PACKED_UINT32 + PACKED_UINT32 + PACKED_UINT32 + PACKED_UINT32)

  NUM_TRAILER_BYTES = TRANSFER_SIZE - PACKED_HEADER.size

  def __init__(self, logger):
    self.next_msg_seq_num = 0

    #TODO: logging
    pass

  def _process_common_header(self, data):
    assert (len(data) == TRANSFER_SIZE)
    #TODO: logging

    #print("dwell_stats: {}".format(data))
    unpacked_header = PACKED_ESM_REPORT_COMMON_HEADER.unpack(data[:PACKED_ESM_REPORT_COMMON_HEADER.size])
    #print(unpacked_header)

    magic_num   = unpacked_header[0]
    msg_seq_num = unpacked_header[1]
    msg_type    = unpacked_header[2]
    mod_id      = unpacked_header[3]

    assert (magic_num == ESM_REPORT_MAGIC_NUM)
    assert (msg_type == ESM_REPORT_MESSAGE_TYPE_DWELL_STATS)
    assert (mod_id in (ESM_MODULE_ID_DWELL_STATS_NARROW, ESM_MODULE_ID_DWELL_STATS_WIDE))

    if msg_seq_num != self.next_msg_seq_num:
      #TODO: logging
      print("Dwell stats seq num gap: expected {}, received {}".format(self.next_msg_seq_num, msg_seq_num))
    self.next_msg_seq_num = (msg_seq_num + 1) & 0xFFFFFFFF

  def process_message(self, data):
    self._process_common_header(data)
    #TODO: is this dwell header scheme reasonable? seems inefficient

    unpacked_header = self.PACKED_HEADER.unpack(data[:self.PACKED_HEADER.size])

    dwell_seq_num           = unpacked_header[4]
    frequency               = unpacked_header[5]
    tag                     = unpacked_header[6]
    duration_requested      = unpacked_header[7]
    report_starting_channel = unpacked_header[8]
    num_channels            = unpacked_header[9]
    fast_lock_profile       = unpacked_header[10]
    gain                    = unpacked_header[11]
    threshold_narrow        = unpacked_header[12]
    threshold_wide          = unpacked_header[13]
    dwell_duration          = unpacked_header[14]
    num_samples             = unpacked_header[15]
    ts_dwell_start          = (unpacked_header[16] << 32) | unpacked_header[17]
    ts_dwell_end            = (unpacked_header[18] << 32) | unpacked_header[19]

    assert (num_channels in (ESM_NUM_CHANNELS_WIDE, ESM_NUM_CHANNELS_NARROW))

    computed_duration = ts_dwell_end - ts_dwell_start
    assert (dwell_duration == computed_duration)  #TODO: remove redundant field

    print("dwell_stats_report: seq={} samples={} ch_start={}   data={}".format(dwell_seq_num, num_samples, report_starting_channel, unpacked_header))

    num_reported_channels = min(self.NUM_TRAILER_BYTES // self.PACKED_CHANNEL_ENTRY.size, num_channels - report_starting_channel)
    for i in range(num_reported_channels):
      unpacked_channel_entry = self.PACKED_CHANNEL_ENTRY.unpack(data[(self.PACKED_HEADER.size + self.PACKED_CHANNEL_ENTRY.size * i) :
                                                                     (self.PACKED_HEADER.size + self.PACKED_CHANNEL_ENTRY.size * (i + 1))])
      channel_index = unpacked_channel_entry[0]
      channel_accum = (unpacked_channel_entry[1] << 32) | unpacked_channel_entry[2]
      channel_max   = unpacked_channel_entry[3]

      assert ((report_starting_channel + i) == channel_index)
      print("  ch[{}]: accum={} peak={}".format(channel_index, channel_accum, channel_max))


    #unpacked_report = self.PACKED_STATUS_REPORT.unpack(data[:self.PACKED_STATUS_REPORT.size])
    #seq_num       = unpacked_report[1]
    #enables_word  = unpacked_report[4]
    #status_word   = unpacked_report[5]
    #timestamp     = (unpacked_report[6] << 32) | unpacked_report[7]
    #
    #print("status_reporter: seq_num={} enables={} status={} timestamp={:x} diff={}".format(seq_num, enables_word, status_word, timestamp, timestamp - self.last_timestamp))
    #
    #self.last_timestamp = timestamp
