import struct
import iio

PACKED_UINT8  = "B"
PACKED_UINT32 = "I"
PACKED_UINT64 = "Q"

ESM_CONTROL_MAGIC_NUM             = 0x45534D43
ESM_MODULE_ID_CONTROL             = 0x00
ESM_CONTROL_MESSAGE_TYPE_ENABLE   = 0x00

class esm_dwell_controller:
  PACKED_ESM_CONFIG = struct.Struct("<" + PACKED_UINT32 + \
                                          PACKED_UINT32 + \
                                          "xx" + PACKED_UINT8 + PACKED_UINT8 + \
                                          PACKED_UINT8 + PACKED_UINT8 + PACKED_UINT8 + PACKED_UINT8)

  TRANSFER_SIZE = 256

  def __init__(self, chan_dma_h2d):
    self.seq_num = 0
    #TODO: logger

    print(chan_dma_h2d.device)
    self.buffer = iio.Buffer(chan_dma_h2d.device, self.TRANSFER_SIZE, False)  #one full buffer per transfer
    print(self.buffer)

  def send_reset(self):
    packed_data = self.PACKED_ESM_CONFIG.pack(ESM_CONTROL_MAGIC_NUM,
                                              self.seq_num,
                                              ESM_MODULE_ID_CONTROL, ESM_CONTROL_MESSAGE_TYPE_ENABLE,
                                              0, 0, 0, 1)
    self.seq_num += 1
    self._send_control(packed_data)

  def send_enables(self, chan_enable, pdw_enable, status_enable):
    packed_data = self.PACKED_ESM_CONFIG.pack(ESM_CONTROL_MAGIC_NUM,
                                              self.seq_num,
                                              ESM_MODULE_ID_CONTROL, ESM_CONTROL_MESSAGE_TYPE_ENABLE,
                                              status_enable, pdw_enable, chan_enable, 0)
    self.seq_num += 1
    self._send_control(packed_data)

  def _send_control(self, data):
    bytes_written = self.buffer.write(bytearray(data))
    if bytes_written == 0:
      raise Exception("failed to write buffer")

    num_words = (bytes_written + 3) // 4
    self.buffer.push(num_words)

    print("wrote {} to buffer ({} bytes -> {} words)".format(data, bytes_written, num_words))
