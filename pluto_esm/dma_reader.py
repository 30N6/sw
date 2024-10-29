import struct
import iio
import esm_status_reporter
import esm_dwell_stats

PACKED_UINT8  = "B"
PACKED_UINT32 = "I"
PACKED_UINT64 = "Q"

ESM_REPORT_MAGIC_NUM                = 0x45534D52
ESM_REPORT_MESSAGE_TYPE_DWELL_STATS = 0x11
ESM_REPORT_MESSAGE_TYPE_PDW_PULSE   = 0x20
ESM_REPORT_MESSAGE_TYPE_PDW_SUMMARY = 0x21
ESM_REPORT_MESSAGE_TYPE_STATUS      = 0x30

class dma_reader:
  PACKED_ESM_REPORT_HEADER = struct.Struct("<" + PACKED_UINT32 + PACKED_UINT32 + "xx" + PACKED_UINT8 + PACKED_UINT8)

  WORD_SIZE = 4
  TRANSFER_SIZE = 256
  TRANSFERS_PER_BUFFER = 16
  BUFFER_SIZE = TRANSFERS_PER_BUFFER*TRANSFER_SIZE // WORD_SIZE

  def __init__(self, chan_dma_d2h):
    #TODO: logger
    self.next_seq_num = 0 #TODO: detect gaps
    self.buffer = iio.Buffer(chan_dma_d2h.device, self.BUFFER_SIZE, False)
    self.buffer.set_blocking_mode(True)

    self.status_reporter  = esm_status_reporter.esm_status_reporter(0)
    self.dwell_stats      = esm_dwell_stats.esm_dwell_stats(0)

  def read(self):
    data = []
    try:
      self.buffer.refill()
      data = self.buffer.read()
      print(data)
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

      unpacked_header = self.PACKED_ESM_REPORT_HEADER.unpack(xfer_data[:self.PACKED_ESM_REPORT_HEADER.size])
      self._process_message(unpacked_header, xfer_data)

  def _process_message(self, header, full_data):
    magic_num = header[0]
    seq_num   = header[1]
    msg_type  = header[2]
    mod_id    = header[3]

    if magic_num != ESM_REPORT_MAGIC_NUM:
      raise RuntimeError("Invalid magic number. header={} full_data={}".format(unpacked_header, full_data))

    if seq_num != self.next_seq_num:
      #TODO: logging
      print("Seq num gap: expected {}, received {}".format(self.next_seq_num, seq_num))

    self.next_seq_num = (seq_num + 1) & 0xFFFFFFFF

    if msg_type == ESM_REPORT_MESSAGE_TYPE_STATUS:
      self.status_reporter.process_message(full_data)
    elif msg_type in (ESM_REPORT_MESSAGE_TYPE_PDW_PULSE, ESM_REPORT_MESSAGE_TYPE_PDW_SUMMARY):
      print("PDW message: not implemented")
    elif msg_type == ESM_REPORT_MESSAGE_TYPE_DWELL_STATS:
      self.dwell_stats.process_message(full_data)

    print(header)