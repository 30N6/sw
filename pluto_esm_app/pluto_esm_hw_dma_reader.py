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
from multiprocessing import Process, Queue, Manager


UDP_PAYLOAD_SIZE  = TRANSFER_SIZE + 4 #includes seq num

class pluto_esm_hw_dma_reader_thread:
  WORD_SIZE = 4
  TRANSFERS_PER_BUFFER = 1 #8 #optimal size unclear -- doesn't matter now with UDP
  BUFFER_SIZE = TRANSFERS_PER_BUFFER*TRANSFER_SIZE // WORD_SIZE

  def __init__(self, arg):
    self.logger         = pluto_esm_logger.pluto_esm_logger(arg["log_dir"], "pluto_esm_hw_dma_rea4der_thread", arg["log_level"])
    self.request_queue  = arg["request_queue"]
    self.result_queue   = arg["result_queue"]

    self.PACKED_UDP_HEADER = struct.Struct(">" + PACKED_UINT32)

    self.next_udp_seq_num = 0
    assert ("ip:" in arg["pluto_uri"])
    self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    self.sock.bind((arg["local_ip"], UDP_FILTER_PORT))
    self.sock.settimeout(0.1)

    recv_buffer_size = self.sock.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)
    self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1048576)
    recv_buffer_size_m = self.sock.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)

    self.logger.log(self.logger.LL_INFO, "init: [UDP mode] queues={}/{} sock={}, current_process={} buf_size={}->{}".format(self.request_queue, self.result_queue, self.sock, multiprocessing.current_process(), recv_buffer_size, recv_buffer_size_m))

    self.logger.flush()

  def _read(self):
    data = []
    udp_seq_num = -1

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

    return udp_seq_num, data

  def run(self):
    running = True
    unique_key = 0

    while running:
      seq_num, data = self._read()
      if len(data) > 0:
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


def pluto_esm_hw_dma_reader_thread_func(arg):
  thread = pluto_esm_hw_dma_reader_thread(arg)
  try:
    thread.run()
  except KeyboardInterrupt:
    thread.shutdown("interrupted")


class pluto_esm_hw_dma_reader:
  def __init__(self, logger, pluto_uri, local_ip, pluto_credentials):
    self.received_data = []
    self.logger = logger
    self.mp_manager           = Manager()
    self.hwdr_request_queue   = Queue() # faster than self.mp_manager.Queue()
    self.hwdr_result_queue    = Queue() # faster than self.mp_manager.Queue()
    self.running = True
    self.num_dma_reads = 0
    self.num_status_reports = 0

    self.output_data_dwell = []
    self.output_data_pdw = []
    self.output_data_status = []

    self.remote_mac = self._get_remote_mac(pluto_uri, pluto_credentials)

    self.hwdr_process = Process(target=pluto_esm_hw_dma_reader_thread_func,
                               args=({"pluto_uri"     : pluto_uri,
                                      "local_ip"      : local_ip,
                                      "request_queue" : self.hwdr_request_queue,
                                      "result_queue"  : self.hwdr_result_queue,
                                      "log_dir"       : logger.path,
                                      "log_level"     : logger.min_level}, ))
    self.hwdr_process.start()

  def _get_remote_mac(self, pluto_uri, pluto_credentials):
    assert ("ip:" in pluto_uri)
    remote_ip = pluto_uri.split(":")[1]
    os_type = platform.system()

    if os_type == "Windows":
      command_list = ["plink", "-pw", pluto_credentials["password"], "{}@{}".format(pluto_credentials["username"], remote_ip), "fw_printenv ethaddr"]
    elif os_type == "Linux":
      command_list = ["sshpass", "-p", pluto_credentials["password"], "ssh", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
        "{}@{}".format(pluto_credentials["username"], remote_ip), "fw_printenv ethaddr"]
    else:
      raise RuntimeError("unsupported OS: {}".format(os_type))

    self.logger.log(self.logger.LL_INFO, "retrieving remote MAC address, command={}".format(command_list))
    r = subprocess.run(command_list, input="n", text=True, capture_output=True) #stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    self.logger.log(self.logger.LL_INFO, "retrieving remote MAC address, returncode={} stdout={}".format(r.returncode, r.stdout))
    self.logger.flush()

    data = r.stdout.strip()
    assert (data.startswith("ethaddr="))
    return data.split("=")[1]

  def _update_receive_queue(self):
    while not self.hwdr_result_queue.empty():
      data = self.hwdr_result_queue.get(block=False)
      self.num_dma_reads += 1
      self.received_data.append(data)
      self.logger.log(self.logger.LL_DEBUG, "[hwdr] _update_receive_queue: received data: len={} uk={} udp_seq_num={}".format(len(data), data["unique_key"], data["udp_seq_num"]))

  def _update_output_queues(self):
    while len(self.received_data) > 0:
      full_data = self.received_data.pop(0)
      udp_seq_num = full_data["udp_seq_num"]
      data = full_data["data"]

      assert ((len(data) % DMA_TRANSFER_SIZE) == 0)
      num_transfers = len(data) // DMA_TRANSFER_SIZE
      for i_xfer in range(num_transfers):
        xfer_data = data[i_xfer*DMA_TRANSFER_SIZE : (i_xfer+1)*DMA_TRANSFER_SIZE]
        unpacked_header = PACKED_ESM_REPORT_COMMON_HEADER.unpack(xfer_data[:PACKED_ESM_REPORT_COMMON_HEADER.size])
        self._process_message(unpacked_header, xfer_data, udp_seq_num)

  def _process_message(self, header, full_data, udp_seq_num):
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
      self.num_status_reports += 1
      self.logger.log(self.logger.LL_DEBUG, "[hwdr] _process_message: saving status message: hw_seq_num={} udp_seq_num={}".format(seq_num, udp_seq_num))
      self.output_data_status.append(full_data)
    elif msg_type in (ESM_REPORT_MESSAGE_TYPE_PDW_PULSE, ESM_REPORT_MESSAGE_TYPE_PDW_SUMMARY):
      self.logger.log(self.logger.LL_DEBUG, "[hwdr] _process_message: saving PDW message: hw_seq_num={} udp_seq_num={}".format(seq_num, udp_seq_num))
      self.output_data_pdw.append(full_data)
    elif msg_type == ESM_REPORT_MESSAGE_TYPE_DWELL_STATS:
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

    self.logger.flush()

    while not self.hwdr_request_queue.empty():
      data = self.hwdr_request_queue.get(block=False)
      self.logger.log(self.logger.LL_INFO, "[hwdr] shutdown: hwdr_request_queue data dropped")
    while not self.hwdr_result_queue.empty():
      data = self.hwdr_result_queue.get(block=False)
      self.logger.log(self.logger.LL_INFO, "[hwdr] shutdown: hwdr_result_queue data dropped")
