import struct
import iio

PACKED_UINT8  = "B"
PACKED_UINT32 = "I"
PACKED_UINT64 = "Q"

ESM_CONTROL_MAGIC_NUM             = 0x45534D43
ESM_MODULE_ID_CONTROL             = 0x00
ESM_CONTROL_MESSAGE_TYPE_ENABLE   = 0x00

class esm_config:
  PACKED_ESM_CONFIG_HEADER  = struct.Struct("<" + PACKED_UINT32 + PACKED_UINT32 + "xx" + PACKED_UINT8 + PACKED_UINT8 + "xxxx")
  PACKED_ESM_CONFIG_CONTROL = struct.Struct("<" + PACKED_UINT32 + PACKED_UINT32 + "xx" + PACKED_UINT8 + PACKED_UINT8 + "xxxx" +
                                                  PACKED_UINT8 + PACKED_UINT8 + PACKED_UINT8 + PACKED_UINT8 + "xxxx")

  TRANSFER_SIZE = 256

  def __init__(self, dma_writer):
    self.seq_num = 0
    self.dma_writer = dma_writer
    #TODO: logger

  def send_reset(self):
    packed_data = self.PACKED_ESM_CONFIG_CONTROL.pack(ESM_CONTROL_MAGIC_NUM,
                                              self.seq_num,
                                              ESM_MODULE_ID_CONTROL, ESM_CONTROL_MESSAGE_TYPE_ENABLE,
                                              0, 0, 0, 1)
    self.seq_num += 1
    self._send_data(packed_data)

  def send_enables(self, chan_enable, pdw_enable, status_enable):
    packed_data = self.PACKED_ESM_CONFIG_CONTROL.pack(ESM_CONTROL_MAGIC_NUM,
                                              self.seq_num,
                                              ESM_MODULE_ID_CONTROL, ESM_CONTROL_MESSAGE_TYPE_ENABLE,
                                              status_enable, pdw_enable, chan_enable, 0)
    self.seq_num += 1
    self._send_data(packed_data)

  def send_module_data(self, mod_id, msg_type, data):
    packed_header = self.PACKED_ESM_CONFIG_HEADER.pack(ESM_CONTROL_MAGIC_NUM, self.seq_num, msg_type, mod_id)
    self.seq_num += 1
    combined_data = packed_header + data
    self._send_data(combined_data)

  def _send_data(self, data):
    num_words = (len(data) + 3) // 4
    if num_words % 2 != 0:
      raise RuntimeError("Odd-length transfer attempted... this probably won't work.")
    self.dma_writer.write(data)


