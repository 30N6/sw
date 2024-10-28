import struct

PACKED_UINT8  = "B"
PACKED_UINT32 = "I"
PACKED_UINT64 = "Q"

class esm_status_reporter:
  PACKED_STATUS_REPORT = struct.Struct("<" + PACKED_UINT32 + PACKED_UINT32 + "xx" + PACKED_UINT8 + PACKED_UINT8 +
                                        PACKED_UINT32 + PACKED_UINT32 + PACKED_UINT64)

  def __init__(self, logger):
    #TODO: logging
    pass

  def process_message(self, data):
    #TODO: logging

    unpacked_report = self.PACKED_STATUS_REPORT.unpack(data[:self.PACKED_STATUS_REPORT.size])
    seq_num       = unpacked_report[1]
    enables_word  = unpacked_report[4]
    status_word   = unpacked_report[5]
    timestamp     = unpacked_report[6]

    print("status_reporter: seq_num={} enables={} status={} timestamp={:x}".format(seq_num, enables_word, status_word, timestamp))
