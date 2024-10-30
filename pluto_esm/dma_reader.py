import struct
import iio
import esm_status_reporter
import esm_dwell_stats
import esm_pdw_encoder
from esm_pkg import *

class dma_reader:
  WORD_SIZE = 4
  TRANSFER_SIZE = 256
  TRANSFERS_PER_BUFFER = 1 #8
  BUFFER_SIZE = TRANSFERS_PER_BUFFER*TRANSFER_SIZE // WORD_SIZE

  def __init__(self, chan_dma_d2h):
    #TODO: logger
    self.buffer = iio.Buffer(chan_dma_d2h.device, self.BUFFER_SIZE, False)
    self.buffer.set_blocking_mode(True)

    self.status_reporter  = esm_status_reporter.esm_status_reporter(0)
    self.dwell_stats      = esm_dwell_stats.esm_dwell_stats(0)
    self.pdw_encoder      = esm_pdw_encoder.esm_pdw_encoder(0)

  def read(self):
    data = []
    try:
      self.buffer.refill()
      data = self.buffer.read()
      #print(data)
      self._process_buffer(data)

    except OSError as e:
      print("timeout -- OSError: {}".format(e))
    except Exception as e:
      print("Exception: {}".format(e))

  def _process_buffer(self, data):
    assert ((len(data) % self.TRANSFER_SIZE) == 0)
    num_transfers = len(data) // self.TRANSFER_SIZE
    #print("len(data)={}  num_transfers={}".format(len(data), num_transfers))

    for i_xfer in range(num_transfers):
      xfer_data = data[i_xfer*self.TRANSFER_SIZE : (i_xfer+1)*self.TRANSFER_SIZE]

      unpacked_header = PACKED_ESM_REPORT_COMMON_HEADER.unpack(xfer_data[:PACKED_ESM_REPORT_COMMON_HEADER.size])
      self._process_message(unpacked_header, xfer_data)

  def _process_message(self, header, full_data):
    magic_num = header[0]
    seq_num   = header[1]
    msg_type  = header[2]
    mod_id    = header[3]

    if magic_num != ESM_REPORT_MAGIC_NUM:
      raise RuntimeError("Invalid magic number. header={} full_data={}".format(unpacked_header, full_data))

    if msg_type == ESM_REPORT_MESSAGE_TYPE_STATUS:
      self.status_reporter.process_message(full_data)
    elif msg_type in (ESM_REPORT_MESSAGE_TYPE_PDW_PULSE, ESM_REPORT_MESSAGE_TYPE_PDW_SUMMARY):
      self.pdw_encoder.process_message(full_data)
    elif msg_type == ESM_REPORT_MESSAGE_TYPE_DWELL_STATS:
      self.dwell_stats.process_message(full_data)
    else:
      raise RuntimeError("unknown message type: {}".format(msg_type))

    #print(header)