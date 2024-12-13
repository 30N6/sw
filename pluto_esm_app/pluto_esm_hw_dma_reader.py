import pluto_esm_logger
from pluto_esm_hw_pkg import *
import os
import iio
import socket
import struct
import time
import platform
import subprocess
import multiprocessing
from multiprocessing import Process, Queue

UDP_PORT          = 50055
UDP_PAYLOAD_SIZE  = TRANSFER_SIZE + 4 #includes seq num

class pluto_esm_hw_dma_reader_thread:
  WORD_SIZE = 4
  #TODO: move to package
  TRANSFERS_PER_BUFFER = 1 #8 TODO: what is the optimal size?
  BUFFER_SIZE = TRANSFERS_PER_BUFFER*TRANSFER_SIZE // WORD_SIZE

  PACKED_UDP_HEADER = struct.Struct("<" + PACKED_UINT32)

  def __init__(self, arg):
    self.logger         = pluto_esm_logger.pluto_esm_logger(arg["log_dir"], "pluto_esm_hw_dma_reader_thread", arg["log_level"])
    self.request_queue  = arg["request_queue"]
    self.result_queue   = arg["result_queue"]
    self.use_udp_dma_rx = arg["use_udp_dma_rx"]

    if self.use_udp_dma_rx:
      self.next_udp_seq_num = 0
      assert ("ip:" in arg["pluto_uri"])
      self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
      self.sock.bind((arg["local_ip"], UDP_PORT))
      self.sock.settimeout(0.1)
      self.logger.log(self.logger.LL_INFO, "init: [UDP mode] queues={}/{} sock={}, current_process={}".format(self.request_queue, self.result_queue, self.sock, multiprocessing.current_process()))
    else:
      self.context        = iio.Context(arg["pluto_uri"])
      self.dev_d2h        = self.context.find_device("axi-iio-dma-d2h")
      self.chan_dma_d2h   = self.dev_d2h.find_channel("voltage0", False)
      #self.dev_d2h.set_kernel_buffers_count(64)
      self.chan_dma_d2h.enabled = True
      self.context.set_timeout(1000)
      self.buffer = iio.Buffer(self.chan_dma_d2h.device, self.BUFFER_SIZE, False)
      self.buffer.set_blocking_mode(True)
      self.logger.log(self.logger.LL_INFO, "init: [IIO mode] queues={}/{} context={} dma_d2h={} buffer={}, current_process={}".format(self.request_queue, self.result_queue, self.context, self.chan_dma_d2h, self.buffer, multiprocessing.current_process()))

  def _read(self):
    data = []
    if self.use_udp_dma_rx:
      try:
        data, addr = self.sock.recvfrom(8192)
        assert (len(data) == UDP_PAYLOAD_SIZE)
        unpacked_header = self.PACKED_UDP_HEADER.unpack(data[:self.PACKED_UDP_HEADER.size])
        udp_seq_num = unpacked_header[0]
        if udp_seq_num != self.next_udp_seq_num:
          self.logger.log(self.logger.LL_WARN, "UDP seq num gap: expected {}, received {}".format(self.next_udp_seq_num, udp_seq_num))
        self.next_udp_seq_num = (udp_seq_num + 1) & 0xFFFFFFFF
        data = data[4:]

      except TimeoutError as e:
        pass

      except Exception as e:
        self.logger.log(self.logger.LL_WARN, "Exception: {}".format(e))

    else:
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
          self.logger.log(self.logger.LL_INFO, "CMD_STOP")
          running = False
        else:
          raise RuntimeError("invalid command")
          running = False

    self.shutdown("graceful exit")

  def shutdown(self, reason):
    self.sock.close()
    self.logger.shutdown(reason)


def pluto_esm_hw_dma_reader_thread_func(arg):
  thread = pluto_esm_hw_dma_reader_thread(arg)
  try:
    thread.run()
  except KeyboardInterrupt:
    thread.shutdown("interrupted")


class pluto_esm_hw_dma_reader_runner_thread:
  def __init__(self, arg):
    self.logger         = pluto_esm_logger.pluto_esm_logger(arg["log_dir"], "pluto_esm_hw_dma_reader_runner_thread", arg["log_level"])
    self.request_queue  = arg["request_queue"]
    self.use_udp_dma_rx = arg["use_udp_dma_rx"]
    self.reader_path    = arg["pluto_dma_reader_path"]
    self.reader_file    = os.path.split(self.reader_path)[-1]
    self.credentials    = arg["pluto_credentials"]
    self.os_type        = platform.system()

    self.dma_reader_process = None

    if self.use_udp_dma_rx:
      assert ("ip:" in arg["pluto_uri"])
      self.local_ip   = arg["local_ip"]
      self.remote_ip  = arg["pluto_uri"].split(":")[1]
      self.logger.log(self.logger.LL_INFO, "init: [UDP mode] local_ip={} remote_ip={} queue={} current_process={}".format(self.local_ip, self.remote_ip, self.request_queue, multiprocessing.current_process()))

      self._kill_dma_reader()
      self._transfer_dma_reader()

    else:
      self.logger.log(self.logger.LL_INFO, "init: [IIO mode] nothing to do...")

  def _kill_dma_reader(self):
    if self.os_type == "Windows":
      command_list = ["plink", "-pw", self.credentials["password"], "{}@{}".format(self.credentials["username"], self.remote_ip), "killall {}".format(self.reader_file)]
    elif self.os_type == "Linux":
      command_list = ["sshpass", "-p", self.credentials["password"], "ssh", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
        "{}@{}".format(self.credentials["username"], self.remote_ip), "killall {}".format(self.reader_file)]
    else:
      raise RuntimeError("unsupported OS: {}".format(os_type))

    self.logger.log(self.logger.LL_INFO, "killing old dma reader instances, command={}".format(command_list))
    r = subprocess.run(command_list, input="n", text=True)
    self.logger.log(self.logger.LL_INFO, "killing old dma reader instances, returncode={}".format(r.returncode))
    self.logger.flush()

  def _transfer_dma_reader(self):
    if self.os_type == "Windows":
      command_list = ["pscp", "-scp", "-pw", self.credentials["password"], self.reader_path, "{}@{}:~/".format(self.credentials["username"], self.remote_ip)]
    elif self.os_type == "Linux":
      command_list = ["sshpass", "-p", self.credentials["password"], "scp", "-O", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
        self.reader_path, "{}@{}:~/".format(self.credentials["username"], self.remote_ip)]
    else:
      raise RuntimeError("unsupported OS: {}".format(os_type))

    self.logger.log(self.logger.LL_INFO, "transferring dma reader, command={}".format(command_list))
    r = subprocess.run(command_list, input="n", text=True)
    self.logger.log(self.logger.LL_INFO, "transferring dma reader, returncode={}".format(r.returncode))
    assert (r.returncode == 0)
    self.logger.flush()

  def run(self):
    if not self.use_udp_dma_rx:
      self.shutdown("use_udp_dma_rx=False")
      return

    if self.os_type == "Windows":
      command_list = ["plink", "-pw", self.credentials["password"], "{}@{}".format(self.credentials["username"], self.remote_ip),
        "chmod +x ./{0}; ./{0} -p local: -c {1}".format(self.reader_file, self.local_ip)]
    elif self.os_type == "Linux":
      command_list = ["sshpass", "-p", self.credentials["password"], "ssh", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
        "{}@{}".format(self.credentials["username"], self.remote_ip),
        "chmod +x ./{0}; ./{0} -p local: -c {1}".format(self.reader_file, self.local_ip)]
    else:
      self.logger.log(self.logger.LL_ERROR, "unsupported OS: {}".format(os_type))
      self.shutdown("error")
      return

    self.logger.log(self.logger.LL_INFO, "starting dma reader, command={}".format(command_list))
    self.dma_reader_process = subprocess.Popen(command_list, text=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    self.dma_reader_process.stdin.write("n\n")
    self.dma_reader_process.stdin.flush()
    self.logger.log(self.logger.LL_INFO, "starting dma reader, p={}".format(self.dma_reader_process))
    self.logger.flush()

    running = True
    while running:
      assert (self.dma_reader_process.poll() is None)
      if not self.request_queue.empty():
        cmd = self.request_queue.get()
        if cmd == "CMD_STOP":
          self.logger.log(self.logger.LL_INFO, "CMD_STOP")
          running = False
        else:
          raise RuntimeError("invalid command")
          running = False
      else:
        time.sleep(0)

    self.shutdown("graceful exit")

  def shutdown(self, reason):
    if self.dma_reader_process is not None:
      self.dma_reader_process.terminate()
      outs, errs = self.dma_reader_process.communicate()
      self.logger.log(self.logger.LL_INFO, "dma reader terminated, p={}".format(self.dma_reader_process))

    self.logger.shutdown(reason)


def pluto_esm_hw_dma_reader_runner_thread_func(arg):
  thread = pluto_esm_hw_dma_reader_runner_thread(arg)

  try:
    thread.run()
  except KeyboardInterrupt:
    thread.shutdown("interrupted")
  except Exception as e:
    thread.shutdown("exception: {}".format(e))


class pluto_esm_hw_dma_reader:
  def __init__(self, logger, pluto_uri, local_ip, pluto_dma_reader_path, pluto_credentials):
    self.received_data = []
    self.pluto_uri = pluto_uri
    self.logger = logger
    self.hwdr_request_queue = Queue()
    self.hwdr_result_queue = Queue()
    self.runner_request_queue = Queue()
    self.running = True

    self.output_data_dwell = []
    self.output_data_pdw = []
    self.output_data_status = []

    self.use_udp_dma_rx = True

    self.runner_process = Process(target=pluto_esm_hw_dma_reader_runner_thread_func,
                               args=({"pluto_uri": pluto_uri, "local_ip": local_ip,
                                      "request_queue": self.runner_request_queue,
                                      "log_dir": logger.path, "log_level": logger.min_level,
                                      "use_udp_dma_rx": self.use_udp_dma_rx,
                                      "pluto_dma_reader_path": pluto_dma_reader_path, "pluto_credentials": pluto_credentials}, ))
    self.runner_process.start()

    self.hwdr_process = Process(target=pluto_esm_hw_dma_reader_thread_func,
                               args=({"pluto_uri": pluto_uri, "local_ip": local_ip,
                                      "request_queue": self.hwdr_request_queue, "result_queue": self.hwdr_result_queue,
                                      "log_dir": logger.path, "log_level": logger.min_level,
                                      "use_udp_dma_rx": self.use_udp_dma_rx}, ))
    self.hwdr_process.start()

  def _update_receive_queue(self):
    while not self.hwdr_result_queue.empty():
      data = self.hwdr_result_queue.get(block=False)
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
    assert (self.hwdr_process.is_alive())
    self._update_receive_queue()
    self._update_output_queues()

  def shutdown(self):
    self.running = False
    self.logger.log(self.logger.LL_INFO, "[hwdr] shutdown")

    if self.hwdr_process.is_alive():
      self.hwdr_request_queue.put("CMD_STOP", block=False)
      self.hwdr_process.join(1.0)
      self.logger.log(self.logger.LL_INFO, "[hwdr] shutdown: hwdr_process.exitcode={} is_alive={}".format(self.hwdr_process.exitcode, self.hwdr_process.is_alive()))
    else:
      self.logger.log(self.logger.LL_INFO, "[hwdr] shutdown: hwdr_process already dead, exitcode={}".format(self.hwdr_process.exitcode))

    if self.runner_process.is_alive():
      self.runner_request_queue.put("CMD_STOP", block=False)
      self.runner_process.join(1.0)
      self.logger.log(self.logger.LL_INFO, "[hwdr] shutdown: runner_process.exitcode={} is_alive={}".format(self.runner_process.exitcode, self.runner_process.is_alive()))
    else:
      self.logger.log(self.logger.LL_INFO, "[hwdr] shutdown: runner_process already dead, exitcode={}".format(self.runner_process.exitcode))

    self.logger.flush()

    while not self.runner_request_queue.empty():
      data = self.runner_request_queue.get(block=False)
      self.logger.log(self.logger.LL_INFO, "[hwdr] shutdown: runner_request_queue data dropped")
    while not self.hwdr_request_queue.empty():
      data = self.hwdr_request_queue.get(block=False)
      self.logger.log(self.logger.LL_INFO, "[hwdr] shutdown: hwdr_request_queue data dropped")
    while not self.hwdr_result_queue.empty():
      data = self.hwdr_result_queue.get(block=False)
      self.logger.log(self.logger.LL_INFO, "[hwdr] shutdown: hwdr_result_queue data dropped")
