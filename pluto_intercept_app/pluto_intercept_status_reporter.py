import struct
import time
from pluto_intercept_hw_pkg import *

class pluto_intercept_status_reporter:
  def __init__(self, logger, status_queue):
    self.logger = logger
    self.status_queue = status_queue
    self.next_seq_num = 0
    self.last_hw_timestamp = 0
    self.last_sw_timestamp = 0

    self.logger.log(self.logger.LL_INFO, "[status_reporter] init")

  def _decode_error(self, data, bit_defs):
    result = []
    for i in range(len(bit_defs)):
      if (data & (0x1 << i)) != 0:
        result.append(bit_defs[i])
    return result

  def _decode_main_status(self, data):
    status_bits = (
      "error_watchdog_timeout",
      "warning_demux_gap",
      "error_chan_demux_overflow",
      "error_chan_filter_overflow",
      "error_chan_mux_overflow",
      "error_chan_mux_underflow",
      "error_chan_mux_collision",
      "error_stream_encoder_fifo_overflow",
      "error_stream_encoder_fifo_underflow",
      "error_stream_encoder_timeout",
      "error_stream_encoder_overflow",
      "error_dwell_stats_timeout",
      "error_dwell_stats_overflow"
    )
    return self._decode_error(data, status_bits)

  def _decode_reporter_status(self, data):
    status_bits = (
      "error_status_reporter_overflow",
      "error_status_reporter_timeout"
    )
    return self._decode_error(data, status_bits)

  def _process_message(self, data):
    unpacked_report = PACKED_STATUS_REPORT.unpack(data[:PACKED_STATUS_REPORT.size])
    seq_num         = unpacked_report[1]
    enables_word    = unpacked_report[4]
    status_main     = unpacked_report[5]
    status_reporter = unpacked_report[6]
    hw_timestamp    = (unpacked_report[7] << 32) | unpacked_report[8]
    sw_timestamp    = time.time()

    self.logger.log(self.logger.LL_INFO, "[status_reporter] seq_num={} enables={} status={},{}  hw_timestamp={} hw_diff={}  sw_timestamp={} sw_diff={}".format(seq_num,
      enables_word, status_main, status_reporter, hw_timestamp, hw_timestamp - self.last_hw_timestamp, sw_timestamp, sw_timestamp - self.last_sw_timestamp))

    if seq_num != self.next_seq_num:
      self.logger.log(self.logger.LL_WARN, "[status_reporter] seq num gap: expected {}, received {}".format(self.next_seq_num, seq_num))
    self.next_seq_num = (seq_num + 1) & 0xFFFFFFFF

    if (status_main != 0) or (status_reporter != 0):
      decoded_main      = self._decode_main_status(status_main)
      decoded_reporter  = self._decode_reporter_status(status_reporter)
      self.logger.log(self.logger.LL_WARN, "[status_reporter] Hardware error detected: {:x} {:x} -- error_bits: {} {}".format(status_main, status_reporter, decoded_main, decoded_reporter))

    self.last_hw_timestamp = hw_timestamp
    self.last_sw_timestamp = time.time()

  def update(self):
    for entry in self.status_queue:
      self._process_message(entry)
    self.status_queue.clear()