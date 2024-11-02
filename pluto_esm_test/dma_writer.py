import iio

class dma_writer:
  TRANSFER_SIZE = 256

  def __init__(self, chan_dma_h2d):
    #TODO: logger
    self.buffer = iio.Buffer(chan_dma_h2d.device, self.TRANSFER_SIZE, False)  #one full buffer per transfer

  def write(self, data):
    bytes_written = self.buffer.write(bytearray(data))
    if bytes_written == 0:
      raise Exception("failed to write buffer")

    num_words = (bytes_written + 3) // 4
    self.buffer.push(num_words)
    print("wrote {} to buffer ({} bytes -> {} words)".format(data, bytes_written, num_words))
