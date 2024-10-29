import struct

PACKED_UINT8  = "B"
PACKED_UINT32 = "I"
PACKED_UINT64 = "Q"

class esm_status_reporter:
  PACKED_STATUS_REPORT = struct.Struct("<" + PACKED_UINT32 + PACKED_UINT32 + "xx" + PACKED_UINT8 + PACKED_UINT8 +
                                        PACKED_UINT32 + PACKED_UINT32 + PACKED_UINT32 + PACKED_UINT32)

  def __init__(self, logger):
    #TODO: logging
    self.next_seq_num = 0
    self.last_timestamp = 0
    pass

  def process_message(self, data):
    #TODO: logging

    unpacked_report = self.PACKED_STATUS_REPORT.unpack(data[:self.PACKED_STATUS_REPORT.size])
    seq_num       = unpacked_report[1]
    enables_word  = unpacked_report[4]
    status_word   = unpacked_report[5]
    timestamp     = (unpacked_report[6] << 32) | unpacked_report[7]

    print("status_reporter: seq_num={} enables={} status={} timestamp={:x} diff={}".format(seq_num, enables_word, status_word, timestamp, timestamp - self.last_timestamp))

    if seq_num != self.next_seq_num:
      #TODO: logging
      print("Status reporter seq num gap: expected {}, received {}".format(self.next_seq_num, seq_num))
    self.next_seq_num = (seq_num + 1) & 0xFFFFFFFF


    if status_word != 0:
      raise RuntimeError("Hardware error detected: {:x}".format(status_word))

    self.last_timestamp = timestamp
