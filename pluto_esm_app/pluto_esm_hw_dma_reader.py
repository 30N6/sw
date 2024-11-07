import pluto_esm_logger
from pluto_esm_hw_pkg import *
import iio
import time
from multiprocessing import Process, Queue

class pluto_esm_hw_dma_reader_thread:
  WORD_SIZE = 4
  #TODO: move to package
  TRANSFERS_PER_BUFFER = 1 #8 TODO: what is the optimal size?
  BUFFER_SIZE = TRANSFERS_PER_BUFFER*TRANSFER_SIZE // WORD_SIZE

  def __init__(self, arg):
    self.logger = pluto_esm_logger.pluto_esm_logger(arg["log_dir"], "pluto_esm_hw_dma_reader_thread", arg["log_level"])
    self.request_queue  = arg["request_queue"]
    self.result_queue   = arg["result_queue"]
    self.context        = iio.Context(arg["pluto_uri"])
    self.dev_d2h        = self.context.find_device("axi-iio-dma-d2h")
    self.chan_dma_d2h   = self.dev_d2h.find_channel("voltage0", False)

    self.chan_dma_d2h.enabled = True
    self.context.set_timeout(1000)

    self.buffer = iio.Buffer(self.chan_dma_d2h.device, self.BUFFER_SIZE, False)
    self.buffer.set_blocking_mode(True)

    self.logger.log(self.logger.LL_INFO, "init: queues={}/{} context={} dma_d2h={} buffer={}".format(self.request_queue, self.result_queue, self.context, self.chan_dma_d2h, self.buffer))

  def _read(self):
    data = []
    try:
      self.buffer.refill()
      data = self.buffer.read()
    except OSError as e:
      self.logger.log(self.logger.LL_WARN, "timeout -- OSError: {}".format(e))
    except Exception as e:
      self.logger.log(self.logger.LL_WARN, "exception: {}".format(e))

    return data

  def run(self):
    running = True
    unique_key = 0

    while running:
      data = self._read()
      if len(data) > 0:
        self.result_queue.put({"unique_key": unique_key, "data": data}, block=False)
        self.logger.log(self.logger.LL_DEBUG, "read {} bytes from buffer - uk={}".format(len(data), unique_key))
        unique_key += 1

      if not self.request_queue.empty():
        cmd = self.request_queue.get()
        if cmd == "CMD_STOP":
          self.logger.log(self.logger.LL_DEBUG, "CMD_STOP")
          running = False
        else:
          raise RuntimeError("invalid command")
          running = False

    self.logger.shutdown("graceful exit")

  def shutdown(self, reason):
    self.logger.shutdown(reason)


def pluto_esm_hw_dma_reader_thread_func(arg):
  thread = pluto_esm_hw_dma_reader_thread(arg)
  try:
    thread.run()
  except KeyboardInterrupt:
    thread.shutdown("interrupted")


class pluto_esm_hw_dma_reader:
  def __init__(self, pluto_uri, logger):
    self.received_data = []
    self.pluto_uri = pluto_uri
    self.logger = logger
    self.request_queue = Queue()
    self.result_queue = Queue()

    self.output_data_dwell = []
    self.output_data_pdw = []
    self.output_data_status = []

    self.hwdr_process = Process(target=pluto_esm_hw_dma_reader_thread_func,
                               args=({"pluto_uri": pluto_uri, "request_queue": self.request_queue, "result_queue": self.result_queue, "log_dir": logger.path, "log_level": logger.min_level}, ))
    self.hwdr_process.start()

  def _update_receive_queue(self):
    while not self.result_queue.empty():
      data = self.result_queue.get(block=False)
      self.received_data.append(data["data"])
      self.logger.log(self.logger.LL_DEBUG, "[hwdr] _update_receive_queue: received data: len={} uk={}".format(len(data), data["unique_key"]))

  def _update_output_queues(self):
    while len(self.received_data) > 0:
      data = self.received_data.pop(0)

      assert ((len(data) % TRANSFER_SIZE) == 0)
      num_transfers = len(data) // TRANSFER_SIZE
      for i_xfer in range(num_transfers):
        xfer_data = data[i_xfer*TRANSFER_SIZE : (i_xfer+1)*TRANSFER_SIZE]
        unpacked_header = PACKED_ESM_REPORT_COMMON_HEADER.unpack(xfer_data[:PACKED_ESM_REPORT_COMMON_HEADER.size])
        self._process_message(unpacked_header, xfer_data)

  def _process_message(self, header, full_data):
    magic_num = header[0]
    seq_num   = header[1]
    msg_type  = header[2]
    mod_id    = header[3]

    if magic_num != ESM_REPORT_MAGIC_NUM:
      #raise RuntimeError("Invalid magic number. header={} full_data={}".format(header, full_data))
      print("Invalid magic number. header={} full_data={}".format(header, full_data))
      self.logger.log(self.logger.LL_ERROR, "[hwdr] Invalid magic number. header={} full_data={}".format(header, full_data))
      return

    if msg_type == ESM_REPORT_MESSAGE_TYPE_STATUS:
      self.logger.log(self.logger.LL_DEBUG, "[hwdr] _process_message: saving status message: seq_num={}".format(seq_num))
      self.output_data_status.append(full_data)
    elif msg_type in (ESM_REPORT_MESSAGE_TYPE_PDW_PULSE, ESM_REPORT_MESSAGE_TYPE_PDW_SUMMARY):
      self.logger.log(self.logger.LL_DEBUG, "[hwdr] _process_message: saving PDW message: seq_num={}".format(seq_num))
      self.output_data_pdw.append(full_data)
    elif msg_type == ESM_REPORT_MESSAGE_TYPE_DWELL_STATS:
      self.logger.log(self.logger.LL_DEBUG, "[hwdr] _process_message: saving dwell message: seq_num={}".format(seq_num))
      self.output_data_dwell.append(full_data)
    else:
      raise RuntimeError("unknown message type: {}".format(msg_type))

  def update(self):
    self._update_receive_queue()
    self._update_output_queues()

  def shutdown(self):
    self.logger.log(self.logger.LL_INFO, "[hwdr] shutdown")
    assert (self.hwdr_process.is_alive())
    self.request_queue.put("CMD_STOP", block=False)
    self.hwdr_process.join(5.0)
    assert (not self.hwdr_process.is_alive())
