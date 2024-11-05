import pluto_esm_logger
from pluto_esm_hw_pkg import *
import iio
import time
from multiprocessing import Process, Pipe

class hw_command:
  CMD_WRITE_ATTR_PHY    = 0
  CMD_WRITE_ATTR_RX_LO  = 1
  CMD_READ_ATTR_PHY     = 2
  CMD_READ_ATTR_RX_LO   = 3
  CMD_WRITE_DMA_H2D     = 4
  CMD_STOP              = 5

  @staticmethod
  def gen_write_attr_phy(unique_key, attr, data):
    cmd = {"unique_key": unique_key, "command_type": hw_command.CMD_WRITE_ATTR_PHY, "attr": attr, "data": data}
    return cmd

  @staticmethod
  def gen_write_attr_rx_lo(unique_key, attr, data):
    return {"unique_key": unique_key, "command_type": hw_command.CMD_WRITE_ATTR_RX_LO, "attr": attr, "data": data}

  @staticmethod
  def gen_read_attr_phy(unique_key, attr):
    return {"unique_key": unique_key, "command_type": hw_command.CMD_READ_ATTR_PHY, "attr": attr, "data": None}

  @staticmethod
  def gen_read_attr_rx_lo(unique_key, attr):
    return {"unique_key": unique_key, "command_type": hw_command.CMD_READ_ATTR_RX_LO, "attr": attr, "data": None}

  @staticmethod
  def gen_write_dma(unique_key, data):
    return {"unique_key": unique_key, "command_type": hw_command.CMD_WRITE_DMA_H2D, "attr": None, "data": data}

  @staticmethod
  def gen_stop():
    return {"unique_key": 0, "command_type": hw_command.CMD_STOP, "attr": None, "data": None}


class pluto_esm_hw_dma_writer:
  def __init__(self, logger, chan_dma_h2d):
    self.logger = logger
    self.buffer = iio.Buffer(chan_dma_h2d.device, TRANSFER_SIZE, False)  #one full buffer per transfer
    self.logger.log(self.logger.LL_INFO, "[hw_dma_writer] init, buffer={}".format(self.buffer))

  def write(self, data):
    bytes_written = self.buffer.write(bytearray(data))
    if bytes_written == 0:
      raise Exception("failed to write buffer")

    num_words = (bytes_written + 3) // 4
    self.buffer.push(num_words)
    self.logger.log(self.logger.LL_DEBUG, "[hw_dma_writer] wrote {} to buffer ({} bytes -> {} words)".format(data, bytes_written, num_words))

class pluto_esm_hw_command_processor_thread:
  def __init__(self, arg):
    #TODO: logging
    self.logger = pluto_esm_logger.pluto_esm_logger(arg["log_dir"], "pluto_esm_hw_command_processor_thread", pluto_esm_logger.pluto_esm_logger.LL_DEBUG)

    self.pipe               = arg["pipe"]
    self.context            = iio.Context(arg["pluto_uri"])
    self.dev_h2d            = self.context.find_device("axi-iio-dma-h2d")
    self.dev_ad9361         = self.context.find_device("ad9361-phy")
    self.chan_dma_h2d       = self.dev_h2d.find_channel("voltage0", True)
    self.chan_ad9361_phy    = self.dev_ad9361.find_channel("voltage0", False)
    self.chan_ad9361_rx_lo  = self.dev_ad9361.find_channel("altvoltage0", True)

    self.chan_dma_h2d.enabled = True
    self.context.set_timeout(1000)

    self.dma_writer = pluto_esm_hw_dma_writer(self.logger, self.chan_dma_h2d)

    self.logger.log(self.logger.LL_INFO, "init: pipe={} context={} dma_h2d={} phy={} rx_lo={}".format(self.pipe, self.context, self.chan_dma_h2d, self.chan_ad9361_phy, self.chan_ad9361_rx_lo))

  def run(self):
    running = True
    while running:
      cmd = self.pipe.recv()
      if cmd["command_type"] == hw_command.CMD_WRITE_ATTR_PHY:
        self.chan_ad9361_phy.attrs[cmd["attr"]].value = cmd["data"]
        self.pipe.send({"unique_key": cmd["unique_key"], "data": None})
        self.logger.log(self.logger.LL_DEBUG, "write phy[{}]={}: uk={}".format(cmd["attr"], cmd["data"], cmd["unique_key"]))

      elif cmd["command_type"] == hw_command.CMD_WRITE_ATTR_RX_LO:
        self.chan_ad9361_rx_lo.attrs[cmd["attr"]].value = cmd["data"]
        self.pipe.send({"unique_key": cmd["unique_key"], "data": None})
        self.logger.log(self.logger.LL_DEBUG, "write rx_lo[{}]={}: uk={}".format(cmd["attr"], cmd["data"], cmd["unique_key"]))

      elif cmd["command_type"] == hw_command.CMD_READ_ATTR_PHY:
        data = self.chan_ad9361_phy.attrs[cmd["attr"]].value
        self.pipe.send({"unique_key": cmd["unique_key"], "data": data})
        self.logger.log(self.logger.LL_DEBUG, "read phy[{}]={}: uk={}".format(cmd["attr"], data, cmd["unique_key"]))

      elif cmd["command_type"] == hw_command.CMD_READ_ATTR_RX_LO:
        data = self.chan_ad9361_rx_lo.attrs[cmd["attr"]].value
        self.pipe.send({"unique_key": cmd["unique_key"], "data": data})
        self.logger.log(self.logger.LL_DEBUG, "read rx_lo[{}]={}: uk={}".format(cmd["attr"], data, cmd["unique_key"]))

      elif cmd["command_type"] == hw_command.CMD_WRITE_DMA_H2D:
        self.dma_writer.write(cmd["data"])
        self.pipe.send({"unique_key": cmd["unique_key"], "data": None})
        self.logger.log(self.logger.LL_DEBUG, "write dma: uk={}".format(cmd["unique_key"]))

      elif cmd["command_type"] == hw_command.CMD_STOP:
        self.logger.log(self.logger.LL_DEBUG, "CMD_STOP")
        running = False

      else:
        raise RuntimeError("invalid command")
        running = False

    self.logger.shutdown("graceful exit")

    def shutdown(self, reason):
      self.logger.shutdown(reason)

def pluto_esm_hw_command_processor_thread_func(arg):
  thread = pluto_esm_hw_command_processor_thread(arg)
  try:
    thread.run()
  except KeyboardInterrupt:
    thread.shutdown("interrupted")


class pluto_esm_hw_command_processor:
  def __init__(self, pluto_uri, logger):
    self.unique_key = 0
    self.received_data = {}
    self.pluto_uri = pluto_uri
    self.logger = logger
    self.master_pipe, slave_pipe = Pipe()

    self.hwc_process = Process(target=pluto_esm_hw_command_processor_thread_func, args=({"pluto_uri": pluto_uri, "pipe": slave_pipe, "log_dir": logger.path}, ))
    self.hwc_process.start()

  def _update_receive_queue(self):
    while self.master_pipe.poll():
      data = self.master_pipe.recv()
      assert (data["unique_key"] not in self.received_data)
      self.received_data[data["unique_key"]] = data

  def send_command(self, cmd):
    self.logger.log(self.logger.LL_DEBUG, "[hwcp] send_command: {}".format(cmd))
    self.master_pipe.send(cmd)

  def try_get_result(self, unique_key):
    self._update_receive_queue()
    if unique_key in self.received_data:
      self.logger.log(self.logger.LL_DEBUG, "[hwcp] try_get_result successful: {}".format(self.received_data[unique_key]))
      return self.received_data.pop(unique_key)
    else:
      return None

  def get_next_unique_key(self):
    k = self.unique_key
    self.unique_key += 1
    return k

  def shutdown(self):
    self.logger.log(self.logger.LL_INFO, "[hwcp] shutdown")
    assert (self.hwc_process.is_alive())
    self.send_command(hw_command.gen_stop())
    self.hwc_process.join(1.0)
    assert (not self.hwc_process.is_alive())


class pluto_esm_hw_config:
  def __init__(self, logger, hwcp):
    self.logger = logger
    self.seq_num = 0
    self.hwcp = hwcp
    self.logger.log(self.logger.LL_INFO, "[hw_cfg] init")

  def send_reset(self):
    self.logger.log(self.logger.LL_DEBUG, "[hw_cfg] send_reset")
    packed_data = PACKED_ESM_CONFIG_CONTROL.pack(ESM_CONTROL_MAGIC_NUM,
                                              self.seq_num,
                                              ESM_MODULE_ID_CONTROL, ESM_CONTROL_MESSAGE_TYPE_ENABLE,
                                              0, 0, 0, 1)
    self.seq_num += 1
    self._send_data(packed_data)

  def send_enables(self, chan_enable, pdw_enable, status_enable):
    self.logger.log(self.logger.LL_DEBUG, "[hw_cfg] send_enables: {} {} {}".format(chan_enable, pdw_enable, status_enable))
    packed_data = PACKED_ESM_CONFIG_CONTROL.pack(ESM_CONTROL_MAGIC_NUM,
                                              self.seq_num,
                                              ESM_MODULE_ID_CONTROL, ESM_CONTROL_MESSAGE_TYPE_ENABLE,
                                              status_enable, pdw_enable, chan_enable, 0)
    self.seq_num += 1
    self._send_data(packed_data)

  def send_module_data(self, mod_id, msg_type, data):
    self.logger.log(self.logger.LL_DEBUG, "[hw_cfg] send_module_data: mod_id={} msg_type={} len(data)={}".format(mod_id, msg_type, len(data)))
    packed_header = PACKED_ESM_CONFIG_HEADER.pack(ESM_CONTROL_MAGIC_NUM, self.seq_num, msg_type, mod_id)
    self.seq_num += 1
    combined_data = packed_header + data
    self._send_data(combined_data)

  def _send_data(self, data):
    num_words = (len(data) + 3) // 4
    if num_words % 2 != 0:
      raise RuntimeError("Odd-length transfer attempted... this probably won't work.")
    cmd = hw_command.gen_write_dma(self.hwcp.get_next_unique_key(), data)
    self.hwcp.send_command(cmd)


class pluto_esm_hw_interface:
  def __init__(self, logger, pluto_uri):
    self.logger = logger

    #todo: iio info
    self.hwcp   = pluto_esm_hw_command_processor(pluto_uri, self.logger)
    self.hw_cfg = pluto_esm_hw_config(self.logger, self.hwcp)
    self.logger.log(self.logger.LL_INFO, "[hwi] init done, hwcp={}".format(self.hwcp))
    #TODO self.dma_reader =

    self.fast_lock_cal_keys = []
    self.fast_lock_cal_freq = 0
    self.fast_lock_cal_pending = False

    self.hw_cfg.send_reset()

  def initial_ad9361_setup(self):
    #TODO
    pass

  def send_fast_lock_cal_cmd(self, frequency):
    self.logger.log(self.logger.LL_INFO, "[hwi] send_fast_lock_cal_cmd: freq={}".format(frequency))

    cmd = []
    cmd.append(hw_command.gen_write_attr_rx_lo(self.hwcp.get_next_unique_key(), "frequency", str(int(frequency * 1e6))))
    cmd.append(hw_command.gen_write_attr_rx_lo(self.hwcp.get_next_unique_key(), "fastlock_store", "0"))
    cmd.append(hw_command.gen_read_attr_rx_lo(self.hwcp.get_next_unique_key(), "fastlock_save"))

    assert (not self.fast_lock_cal_pending)
    self.fast_lock_cal_pending  = True
    self.fast_lock_cal_keys     = [c["unique_key"] for c in cmd]
    self.fast_lock_cal_freq     = frequency

    for entry in cmd:
      self.hwcp.send_command(entry)

  def check_fast_lock_cal_results(self):
    assert (self.fast_lock_cal_pending)
    cmd_result = self.hwcp.try_get_result(self.fast_lock_cal_keys[0])

    if cmd_result is not None:
      finished_key = self.fast_lock_cal_keys.pop(0)
      assert (cmd_result["unique_key"] == finished_key)
      if len(self.fast_lock_cal_keys) == 0:
        self.fast_lock_cal_pending = False
        return {"freq": self.fast_lock_cal_freq, "data": cmd_result["data"]}

    return None

  def test(self):
    for freq in range(500, 5000, 100):
      cmd = hw_command.gen_write_attr_rx_lo(self.hwcp.get_next_unique_key(), "frequency", str(int(freq * 1e6)))
      start_time = time.time()
      print("[{}] sending command: {}".format(start_time, cmd))
      self.hwcp.send_command(cmd)
      r = None
      while r is None:
        r = self.hwcp.try_get_result(cmd["unique_key"])
      end_time = time.time()
      print("[{}] command complete: {} -- diff={}".format(end_time, r, end_time - start_time))

    #start_time = time.time()
    #keys = []
    #for freq in range(500, 5000, 100):
    #  cmd = hw_command.gen_write_attr_rx_lo(self.hwcp.get_next_unique_key(), "frequency", str(int(freq * 1e6)))
    #  print("[{}] sending command: {}".format(start_time, cmd))
    #  self.hwcp.send_command(cmd)
    #  keys.append(cmd["unique_key"])
    #
    #for k in keys:
    #  r = None
    #  while r is None:
    #    r = self.hwcp.try_get_result(k)
    #  end_time = time.time()
    #  print("[{}] command complete: {} -- diff={}".format(end_time, r, end_time - start_time))



  def shutdown(self):
    self.hwcp.shutdown()
