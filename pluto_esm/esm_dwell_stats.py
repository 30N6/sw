import struct

PACKED_UINT8  = "B"
PACKED_UINT16 = "H"
PACKED_UINT32 = "I"
PACKED_UINT64 = "Q"

class esm_dwell_stats:
  PACKED_HEADER = struct.Struct("<" + PACKED_UINT32 + PACKED_UINT32 + "xx" + PACKED_UINT8 + PACKED_UINT8 +
                                      PACKED_UINT32 +
                                      PACKED_UINT16 + PACKED_UINT16 +
                                      PACKED_UINT32 +
                                      "xx" + PACKED_UINT8 + PACKED_UINT8 +
                                      PACKED_UINT32 +
                                      PACKED_UINT32 +
                                      "xxxxxxxx" + "xxxx" +
                                      PACKED_UINT32 +
                                      PACKED_UINT32 +
                                      PACKED_UINT32 + PACKED_UINT32 +
                                      PACKED_UINT32 + PACKED_UINT32)

  PACKED_CHANNEL_ENTRY = struct.Struct("<" + PACKED_UINT32 + PACKED_UINT32 + PACKED_UINT32 + PACKED_UINT32)

  def __init__(self, logger):
    #TODO: logging
    pass

  def process_message(self, data):
    #TODO: logging
    #TODO: is this dwell header scheme reasonable? seems inefficient

    print("dwell_stats: {}".format(data))

    unpacked_header = self.PACKED_HEADER.unpack(data[:self.PACKED_HEADER.size])
    print(unpacked_header)

    #unpacked_report = self.PACKED_STATUS_REPORT.unpack(data[:self.PACKED_STATUS_REPORT.size])
    #seq_num       = unpacked_report[1]
    #enables_word  = unpacked_report[4]
    #status_word   = unpacked_report[5]
    #timestamp     = (unpacked_report[6] << 32) | unpacked_report[7]
    #
    #print("status_reporter: seq_num={} enables={} status={} timestamp={:x} diff={}".format(seq_num, enables_word, status_word, timestamp, timestamp - self.last_timestamp))
    #
    #self.last_timestamp = timestamp
