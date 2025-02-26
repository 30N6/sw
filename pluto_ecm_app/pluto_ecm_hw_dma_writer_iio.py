import pluto_ecm_logger
from pluto_ecm_hw_pkg import *
import iio

class pluto_ecm_hw_dma_writer_iio:
  def __init__(self, logger, context):
    self.logger = logger

    self.dev_h2d              = context.find_device("axi-iio-dma-h2d")
    self.chan_dma_h2d         = self.dev_h2d.find_channel("voltage0", True)
    self.chan_dma_h2d.enabled = True

    self.buffer = iio.Buffer(self.chan_dma_h2d.device, DMA_TRANSFER_SIZE, False)  #one full buffer per transfer
    self.logger.log(self.logger.LL_INFO, "[hw_dma_writer_iio] init, buffer={}".format(self.buffer))

  def write(self, data):
    bytes_written = self.buffer.write(bytearray(data))
    if bytes_written == 0:
      raise Exception("failed to write buffer")

    num_words = (bytes_written + 3) // 4
    self.buffer.push(num_words)
    self.logger.log(self.logger.LL_DEBUG, "[hw_dma_writer_iio] wrote {} to buffer ({} bytes -> {} words)".format(data, bytes_written, num_words))
