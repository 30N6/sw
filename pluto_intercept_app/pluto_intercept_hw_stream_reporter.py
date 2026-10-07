import numpy as np

from pluto_intercept_hw_pkg import *

class pluto_intercept_hw_stream_reporter:
  def __init__(self, logger):
    self.logger = logger
    self.next_msg_seq_num = 0

    self.logger.log(self.logger.LL_INFO, "[pluto_intercept_hw_stream_reporter] init")

  def _process_common_header(self, data):
    unpacked_header = PACKED_INTERCEPT_REPORT_COMMON_HEADER.unpack(data[:PACKED_INTERCEPT_REPORT_COMMON_HEADER.size])

    magic_num   = unpacked_header[0]
    msg_seq_num = unpacked_header[1]
    msg_type    = unpacked_header[2]
    mod_id      = unpacked_header[3]

    assert (magic_num == INTERCEPT_REPORT_MAGIC_NUM)
    assert (msg_type == INTERCEPT_REPORT_MESSAGE_TYPE_STREAM)
    assert (mod_id == INTERCEPT_MODULE_ID_STREAM_ENCODER)

    if msg_seq_num != self.next_msg_seq_num:
      self.logger.log(self.logger.LL_WARN, "Stream encoder seq num gap: expected {}, received {}".format(self.next_msg_seq_num, msg_seq_num))
    self.next_msg_seq_num = (msg_seq_num + 1) & 0xFFFFFFFF

    return msg_type

  def process_message(self, data):
    self._process_common_header(data)

    unpacked_header = PACKED_STREAM_HEADER.unpack(data[:PACKED_STREAM_HEADER.size])

    report = {}

    report["msg_seq_num"]           = unpacked_header[1]
    report["msg_type"]              = unpacked_header[2]

    report["dwell_seq_num"]         = unpacked_header[4]
    report["dwell_tag"]             = unpacked_header[5]
    report["dwell_frequency"]       = unpacked_header[6]
    report["dwell_window_duration"] = unpacked_header[7]
    report["timestamp"]             = (unpacked_header[8] << 32) | unpacked_header[9]

    trailer_bytes = len(data) - PACKED_STREAM_HEADER.size
    num_reported_samples = trailer_bytes // PACKED_STREAM_SAMPLE.size

    offset = PACKED_STREAM_HEADER.size
    nbytes = num_reported_samples * PACKED_STREAM_SAMPLE_DTYPE.itemsize
    raw = data[offset:offset + nbytes]

    report["stream_samples"] = np.frombuffer(raw, dtype=PACKED_STREAM_SAMPLE_DTYPE, count=num_reported_samples)

    return report

