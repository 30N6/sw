import struct
from esm_pkg import *

class esm_status_reporter:
  PACKED_STATUS_REPORT = struct.Struct("<" + PACKED_UINT32 + PACKED_UINT32 + "xx" + PACKED_UINT8 + PACKED_UINT8 +
                                        PACKED_UINT32 + PACKED_UINT32 + PACKED_UINT32 + PACKED_UINT32 + PACKED_UINT32 + PACKED_UINT32)

  def __init__(self, logger):
    #TODO: logging
    self.next_seq_num = 0
    self.last_timestamp = 0
    pass

  def _decode_error(self, data, bit_defs):
    result = []
    for i in range(len(bit_defs)):
      if (data & (0x1 << i)) != 0:
        result.append(bit_defs[i])
    return result

  def _decode_path_status(self, data):
    status_bits = (
      "warning_demux_gap",
      "error_demux_overflow",
      "error_filter_overflow",
      "error_mux_overflow",
      "error_mux_underflow",
      "error_mux_collision",
      "error_dwell_reporter_timeout",
      "error_dwell_reporter_overflow",
      "error_pdw_fifo_busy",
      "error_pdw_fifo_overflow",
      "error_pdw_fifo_underflow",
      "error_pdw_sample_buffer_busy",
      "error_pdw_sample_buffer_underflow",
      "error_pdw_sample_buffer_overflow",
      "error_pdw_reporter_timeout",
      "error_pdw_reporter_overflow"
    )
    return self._decode_error(data, status_bits)

  def _decode_reporter_status(self, data):
    status_bits = (
      "error_status_reporter_overflow",
      "error_status_reporter_timeout"
    )
    return self._decode_error(data, status_bits)

  def process_message(self, data):
    #TODO: logging

    unpacked_report = self.PACKED_STATUS_REPORT.unpack(data[:self.PACKED_STATUS_REPORT.size])
    seq_num         = unpacked_report[1]
    enables_word    = unpacked_report[4]
    status_path_0   = unpacked_report[5]
    status_path_1   = unpacked_report[6]
    status_reporter = unpacked_report[7]

    timestamp       = (unpacked_report[8] << 32) | unpacked_report[9]

    print("status_reporter: seq_num={} enables={} status={},{},{} timestamp={:x} diff={}".format(seq_num,
      enables_word, status_path_0, status_path_1, status_reporter, timestamp, timestamp - self.last_timestamp))

    if seq_num != self.next_seq_num:
      #TODO: logging
      print("Status reporter seq num gap: expected {}, received {}".format(self.next_seq_num, seq_num))
    self.next_seq_num = (seq_num + 1) & 0xFFFFFFFF

    if (status_path_0 != 0) or (status_path_1 != 0) or (status_reporter != 0):
      decoded_path_0    = self._decode_path_status(status_path_0)
      decoded_path_1    = self._decode_path_status(status_path_1)
      decoded_reporter  = self._decode_reporter_status(status_reporter)
      #raise RuntimeError("Hardware error detected: {:x}".format(status_word))
      print("Hardware error detected: {:x} {:x} {:x}".format(status_path_0, status_path_1, status_reporter))
      print("  error bits: {} {} {}".format(decoded_path_0, decoded_path_1, decoded_reporter))
      exit()

    self.last_timestamp = timestamp
