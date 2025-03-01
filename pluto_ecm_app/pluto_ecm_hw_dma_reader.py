import pluto_ecm_logger
from pluto_ecm_hw_pkg import *
import os
import iio
import socket
import struct
import time
import platform
import subprocess
import multiprocessing
from multiprocessing import Process, Queue


UDP_PAYLOAD_SIZE = DMA_TRANSFER_SIZE + 4 #includes seq num

class pluto_ecm_hw_dma_reader_thread:
  WORD_SIZE = 4
  TRANSFERS_PER_BUFFER = 1 #8 #optimal size unclear -- doesn't matter now with UDP
  BUFFER_SIZE = TRANSFERS_PER_BUFFER*DMA_TRANSFER_SIZE // WORD_SIZE


  def __init__(self, arg):
    self.logger         = pluto_ecm_logger.pluto_ecm_logger(arg["log_dir"], "pluto_ecm_hw_dma_reader_thread", arg["log_level"])
    self.request_queue  = arg["request_queue"]
    self.result_queue   = arg["result_queue"]
    self.use_udp_dma_rx = arg["use_udp_dma_rx"]
    self.direct_udp_tx  = arg["direct_udp_tx"]

    if self.direct_udp_tx:
      self.udp_port = UDP_FILTER_PORT
      self.PACKED_UDP_HEADER = struct.Struct(">" + PACKED_UINT32)
    else:
      self.udp_port = 50055
      self.PACKED_UDP_HEADER = struct.Struct("<" + PACKED_UINT32)

    if self.use_udp_dma_rx:
      self.next_udp_seq_num = 0
      assert ("ip:" in arg["pluto_uri"])
      self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
      self.sock.bind((arg["local_ip"], self.udp_port))
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

    self.logger.flush()

  def _read(self):
    data = []
    udp_seq_num = -1
    if self.use_udp_dma_rx:
      try:
        data, addr = self.sock.recvfrom(8192)
        #self.logger.log(self.logger.LL_INFO, "_read: data received: addr={} len={}".format(addr, len(data)))
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

    return udp_seq_num, data

  def run(self):
    running = True
    unique_key = 0
    startup_flush = not self.direct_udp_tx  #not needed for direct UDP

    while running:
      seq_num, data = self._read()
      if len(data) > 0:
        if startup_flush:
          if seq_num == 0:
            startup_flush = False
            self.logger.log(self.logger.LL_INFO, "[startup] seq={} received - flush complete".format(seq_num))
          else:
            self.logger.log(self.logger.LL_INFO, "[startup] dropping data: seq={} - read {} bytes from buffer".format(seq_num, len(data)))
            continue

        self.result_queue.put({"unique_key": unique_key, "data": data, "udp_seq_num": seq_num}, block=False)
        self.logger.log(self.logger.LL_DEBUG, "seq={} - read {} bytes from buffer - uk={}".format(seq_num, len(data), unique_key))
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


def pluto_ecm_hw_dma_reader_thread_func(arg):
  thread = pluto_ecm_hw_dma_reader_thread(arg)
  try:
    thread.run()
  except KeyboardInterrupt:
    thread.shutdown("interrupted")


class pluto_ecm_hw_dma_reader_runner_thread:
  def __init__(self, arg):
    self.logger         = pluto_ecm_logger.pluto_ecm_logger(arg["log_dir"], "pluto_ecm_hw_dma_reader_runner_thread", arg["log_level"])
    self.request_queue  = arg["request_queue"]
    self.result_queue   = arg["result_queue"]
    self.use_udp_dma_rx = arg["use_udp_dma_rx"]
    self.direct_udp_tx  = arg["direct_udp_tx"]
    self.reader_path    = arg["pluto_dma_reader_path"]
    self.reader_file    = os.path.split(self.reader_path)[-1]
    self.credentials    = arg["pluto_credentials"]
    self.os_type        = platform.system()

    self.dma_reader_process = None

    if self.direct_udp_tx:
      assert ("ip:" in arg["pluto_uri"])
      self.local_ip   = arg["local_ip"]
      self.remote_ip  = arg["pluto_uri"].split(":")[1]
      self.logger.log(self.logger.LL_INFO, "init: [UDP mode - direct] local_ip={} remote_ip={} queue={} current_process={}".format(self.local_ip, self.remote_ip, self.request_queue, multiprocessing.current_process()))

      self._get_remote_mac()

    elif self.use_udp_dma_rx:
      assert ("ip:" in arg["pluto_uri"])
      self.local_ip   = arg["local_ip"]
      self.remote_ip  = arg["pluto_uri"].split(":")[1]
      self.logger.log(self.logger.LL_INFO, "init: [UDP mode - indirect] local_ip={} remote_ip={} queue={} current_process={}".format(self.local_ip, self.remote_ip, self.request_queue, multiprocessing.current_process()))

      self._kill_dma_reader()
      self._transfer_dma_reader()

    else:
      self.logger.log(self.logger.LL_INFO, "init: [IIO mode] nothing to do...")

  def _get_remote_mac(self):
    if self.os_type == "Windows":
      command_list = ["plink", "-pw", self.credentials["password"], "{}@{}".format(self.credentials["username"], self.remote_ip), "fw_printenv ethaddr"]
    elif self.os_type == "Linux":
      command_list = ["sshpass", "-p", self.credentials["password"], "ssh", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
        "{}@{}".format(self.credentials["username"], self.remote_ip), "fw_printenv ethaddr"]
    else:
      raise RuntimeError("unsupported OS: {}".format(os_type))

    self.logger.log(self.logger.LL_INFO, "retrieving remote MAC address, command={}".format(command_list))
    r = subprocess.run(command_list, input="n", text=True, capture_output=True) #stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    self.logger.log(self.logger.LL_INFO, "retrieving remote MAC address, returncode={} stdout={}".format(r.returncode, r.stdout))
    self.logger.flush()

    self.result_queue.put(r.stdout.strip())

  def _kill_dma_reader(self):
    if self.os_type == "Windows":
      command_list = ["plink", "-pw", self.credentials["password"], "{}@{}".format(self.credentials["username"], self.remote_ip), "killall {}".format(self.reader_file)]
    elif self.os_type == "Linux":
      command_list = ["sshpass", "-p", self.credentials["password"], "ssh", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
        "{}@{}".format(self.credentials["username"], self.remote_ip), "killall {}".format(self.reader_file)]
    else:
      raise RuntimeError("unsupported OS: {}".format(os_type))

    self.logger.log(self.logger.LL_INFO, "killing old dma reader instances, command={}".format(command_list))
    r = subprocess.run(command_list, input="n", text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
    r = subprocess.run(command_list, input="n", text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    self.logger.log(self.logger.LL_INFO, "transferring dma reader, returncode={}".format(r.returncode))
    assert (r.returncode == 0)
    self.logger.flush()

  def run(self):
    if not self.use_udp_dma_rx:
      self.shutdown("use_udp_dma_rx=False")
      return

    if self.direct_udp_tx:
      self.shutdown("direct_udp_tx=True")
      return

    if self.os_type == "Windows":
      command_list = ["plink", "-pw", self.credentials["password"], "{}@{}".format(self.credentials["username"], self.remote_ip),
        "chmod +x ./{0}; ./{0} -p local: -c {1} -b {2}".format(self.reader_file, self.local_ip, ECM_WORDS_PER_DMA_PACKET)]
    elif self.os_type == "Linux":
      command_list = ["sshpass", "-p", self.credentials["password"], "ssh", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
        "{}@{}".format(self.credentials["username"], self.remote_ip),
        "chmod +x ./{0}; ./{0} -p local: -c {1} -b {2}".format(self.reader_file, self.local_ip, ECM_WORDS_PER_DMA_PACKET)]
    else:
      self.logger.log(self.logger.LL_ERROR, "unsupported OS: {}".format(os_type))
      self.shutdown("error")
      return

    self.logger.log(self.logger.LL_INFO, "starting dma reader, command={}".format(command_list))
    self.dma_reader_process = subprocess.Popen(command_list, text=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
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


def pluto_ecm_hw_dma_reader_runner_thread_func(arg):
  thread = pluto_ecm_hw_dma_reader_runner_thread(arg)

  try:
    thread.run()
  except KeyboardInterrupt:
    thread.shutdown("interrupted")
  except Exception as e:
    thread.shutdown("exception: {}".format(e))


class pluto_ecm_hw_dma_reader:
  def __init__(self, logger, pluto_uri, local_ip, pluto_dma_reader_path, pluto_credentials, udp_mode):
    self.received_data = []
    self.pluto_uri = pluto_uri
    self.logger = logger
    self.udp_mode = udp_mode
    self.hwdr_request_queue = Queue()
    self.hwdr_result_queue = Queue()
    self.runner_request_queue = Queue()
    self.runner_result_queue = Queue()
    self.running = True
    self.num_dma_reads = 0
    self.num_status_reports = 0

    self.output_data_dwell = []
    self.output_data_drfm = []
    self.output_data_status = []

    self.use_udp_dma_rx = True
    self.remote_mac = None

    self.runner_process = Process(target=pluto_ecm_hw_dma_reader_runner_thread_func,
                               args=({"pluto_uri"             : pluto_uri,
                                      "local_ip"              : local_ip,
                                      "request_queue"         : self.runner_request_queue,
                                      "result_queue"          : self.runner_result_queue,
                                      "log_dir"               : logger.path,
                                      "log_level"             : logger.min_level,
                                      "use_udp_dma_rx"        : self.use_udp_dma_rx,
                                      "direct_udp_tx"         : self.udp_mode,
                                      "pluto_dma_reader_path" : pluto_dma_reader_path,
                                      "pluto_credentials"     : pluto_credentials}, ))
    self.runner_process.start()

    self.hwdr_process = Process(target=pluto_ecm_hw_dma_reader_thread_func,
                               args=({"pluto_uri"       : pluto_uri,
                                      "local_ip"        : local_ip,
                                      "request_queue"   : self.hwdr_request_queue,
                                      "result_queue"    : self.hwdr_result_queue,
                                      "log_dir"         : logger.path,
                                      "log_level"       : logger.min_level,
                                      "use_udp_dma_rx"  : self.use_udp_dma_rx,
                                      "direct_udp_tx"   : self.udp_mode,}, ))
    self.hwdr_process.start()

  def _update_receive_queue(self):
    while not self.hwdr_result_queue.empty():
      data = self.hwdr_result_queue.get(block=False)
      self.num_dma_reads += 1
      self.received_data.append(data)
      self.logger.log(self.logger.LL_DEBUG, "[hwdr] _update_receive_queue: received data: len={} uk={} udp_seq_num={}".format(len(data), data["unique_key"], data["udp_seq_num"]))

    if self.udp_mode and (self.remote_mac is None):
      while not self.runner_result_queue.empty():
        data = self.runner_result_queue.get(block=False)
        self.logger.log(self.logger.LL_INFO, "[hwdr] _update_receive_queue: data from DMA runner: {}".format(data))
        self.logger.flush()
        assert (data.startswith("ethaddr="))
        self.remote_mac = data.split("=")[1]

  def _update_output_queues(self):
    while len(self.received_data) > 0:
      full_data = self.received_data.pop(0)
      udp_seq_num = full_data["udp_seq_num"]
      data = full_data["data"]

      assert ((len(data) % DMA_TRANSFER_SIZE) == 0)
      num_transfers = len(data) // DMA_TRANSFER_SIZE
      for i_xfer in range(num_transfers):
        xfer_data = data[i_xfer*DMA_TRANSFER_SIZE : (i_xfer+1)*DMA_TRANSFER_SIZE]
        unpacked_header = PACKED_ECM_REPORT_COMMON_HEADER.unpack(xfer_data[:PACKED_ECM_REPORT_COMMON_HEADER.size])
        self._process_message(unpacked_header, xfer_data, udp_seq_num)

  def _process_message(self, header, full_data, udp_seq_num):
    magic_num = header[0]
    seq_num   = header[1]
    msg_type  = header[2]
    mod_id    = header[3]

    if magic_num != ECM_REPORT_MAGIC_NUM:
      print("Invalid magic number. header={} full_data={}".format(header, full_data))
      self.logger.log(self.logger.LL_ERROR, "[hwdr] Invalid magic number. header={} full_data={}".format(header, full_data))
      return

    if msg_type == ECM_REPORT_MESSAGE_TYPE_STATUS:
      self.num_status_reports += 1
      self.logger.log(self.logger.LL_DEBUG, "[hwdr] _process_message: saving status message: hw_seq_num={} udp_seq_num={}".format(seq_num, udp_seq_num))
      self.output_data_status.append(full_data)
    elif msg_type in (ECM_REPORT_MESSAGE_TYPE_DRFM_CHANNEL_DATA, ECM_REPORT_MESSAGE_TYPE_DRFM_SUMMARY):
      self.logger.log(self.logger.LL_DEBUG, "[hwdr] _process_message: saving DRFM message: hw_seq_num={} udp_seq_num={}".format(seq_num, udp_seq_num))
      self.output_data_drfm.append(full_data)
    elif msg_type == ECM_REPORT_MESSAGE_TYPE_DWELL_STATS:
      self.logger.log(self.logger.LL_DEBUG, "[hwdr] _process_message: saving dwell message: hw_seq_num={} udp_seq_num={}".format(seq_num, udp_seq_num))
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
