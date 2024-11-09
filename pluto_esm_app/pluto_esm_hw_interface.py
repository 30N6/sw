import pluto_esm_logger
import pluto_esm_hw_dma_reader
import pluto_esm_status_reporter
from pluto_esm_hw_pkg import *
import iio
import time
from multiprocessing import Process, Queue

class hw_command:
  CMD_WRITE_ATTR_PHY    = 0
  CMD_WRITE_ATTR_RX_LO  = 1
  CMD_WRITE_ATTR_DBG    = 2
  CMD_READ_ATTR_PHY     = 3
  CMD_READ_ATTR_RX_LO   = 4
  CMD_WRITE_DMA_H2D     = 5
  CMD_STOP              = 6

  @staticmethod
  def gen_write_attr_phy(unique_key, attr, data):
    cmd = {"unique_key": unique_key, "command_type": hw_command.CMD_WRITE_ATTR_PHY, "attr": attr, "data": data}
    return cmd

  @staticmethod
  def gen_write_attr_rx_lo(unique_key, attr, data):
    return {"unique_key": unique_key, "command_type": hw_command.CMD_WRITE_ATTR_RX_LO, "attr": attr, "data": data}

  @staticmethod
  def gen_write_attr_dbg(unique_key, attr, data):
    return {"unique_key": unique_key, "command_type": hw_command.CMD_WRITE_ATTR_DBG, "attr": attr, "data": data}

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
    self.logger = pluto_esm_logger.pluto_esm_logger(arg["log_dir"], "pluto_esm_hw_command_processor_thread", pluto_esm_logger.pluto_esm_logger.LL_DEBUG)  #TODO: log level via arg

    self.request_queue      = arg["request_queue"]
    self.result_queue       = arg["result_queue"]
    self.context            = iio.Context(arg["pluto_uri"])
    self.dev_h2d            = self.context.find_device("axi-iio-dma-h2d")
    self.dev_ad9361         = self.context.find_device("ad9361-phy")
    self.chan_dma_h2d       = self.dev_h2d.find_channel("voltage0", True)
    self.chan_ad9361_phy    = self.dev_ad9361.find_channel("voltage0", False)
    self.chan_ad9361_rx_lo  = self.dev_ad9361.find_channel("altvoltage0", True)

    self.chan_dma_h2d.enabled = True
    self.context.set_timeout(1000)

    self.dma_writer = pluto_esm_hw_dma_writer(self.logger, self.chan_dma_h2d)

    self.logger.log(self.logger.LL_INFO, "init: queues={}/{} context={} dma_h2d={} phy={} rx_lo={}".format(self.request_queue, self.result_queue, self.context, self.chan_dma_h2d, self.chan_ad9361_phy, self.chan_ad9361_rx_lo))

  def run(self):
    running = True
    while running:
      self.logger.log(self.logger.LL_DEBUG, "request_queue.get() start")
      cmd = self.request_queue.get()
      t_start = time.time()
      self.logger.log(self.logger.LL_DEBUG, "command_start")
      if cmd["command_type"] == hw_command.CMD_WRITE_ATTR_PHY:
        self.chan_ad9361_phy.attrs[cmd["attr"]].value = cmd["data"]
        self.result_queue.put({"unique_key": cmd["unique_key"], "data": None}, block=False)
        self.logger.log(self.logger.LL_DEBUG, "write phy[{}]={}: uk={}".format(cmd["attr"], cmd["data"], cmd["unique_key"]))

      elif cmd["command_type"] == hw_command.CMD_WRITE_ATTR_RX_LO:
        self.chan_ad9361_rx_lo.attrs[cmd["attr"]].value = cmd["data"]
        self.result_queue.put({"unique_key": cmd["unique_key"], "data": None}, block=False)
        self.logger.log(self.logger.LL_DEBUG, "write rx_lo[{}]={}: uk={}".format(cmd["attr"], cmd["data"], cmd["unique_key"]))

      elif cmd["command_type"] == hw_command.CMD_WRITE_ATTR_DBG:
        self.dev_ad9361.debug_attrs[cmd["attr"]].value = cmd["data"]
        self.result_queue.put({"unique_key": cmd["unique_key"], "data": None}, block=False)
        self.logger.log(self.logger.LL_DEBUG, "write dbg[{}]={}: uk={}".format(cmd["attr"], cmd["data"], cmd["unique_key"]))

      elif cmd["command_type"] == hw_command.CMD_READ_ATTR_PHY:
        data = self.chan_ad9361_phy.attrs[cmd["attr"]].value
        self.result_queue.put({"unique_key": cmd["unique_key"], "data": data}, block=False)
        self.logger.log(self.logger.LL_DEBUG, "read phy[{}]={}: uk={}".format(cmd["attr"], data, cmd["unique_key"]))

      elif cmd["command_type"] == hw_command.CMD_READ_ATTR_RX_LO:
        data = self.chan_ad9361_rx_lo.attrs[cmd["attr"]].value
        self.result_queue.put({"unique_key": cmd["unique_key"], "data": data}, block=False)
        self.logger.log(self.logger.LL_DEBUG, "read rx_lo[{}]={}: uk={}".format(cmd["attr"], data, cmd["unique_key"]))

      elif cmd["command_type"] == hw_command.CMD_WRITE_DMA_H2D:
        self.dma_writer.write(cmd["data"])
        self.result_queue.put({"unique_key": cmd["unique_key"], "data": None}, block=False)
        self.logger.log(self.logger.LL_DEBUG, "write dma: uk={}".format(cmd["unique_key"]))

      elif cmd["command_type"] == hw_command.CMD_STOP:
        self.logger.log(self.logger.LL_DEBUG, "CMD_STOP")
        running = False

      else:
        raise RuntimeError("invalid command")
        running = False

      self.logger.log(self.logger.LL_DEBUG, "command_end: diff={}".format(time.time() - t_start))

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
    self.ack_not_expected = []
    self.pluto_uri = pluto_uri
    self.logger = logger

    self.request_queue = Queue()
    self.result_queue = Queue()

    self.hwc_process = Process(target=pluto_esm_hw_command_processor_thread_func, args=({"pluto_uri": pluto_uri, "request_queue": self.request_queue, "result_queue": self.result_queue, "log_dir": logger.path}, ))
    self.hwc_process.start()

  def _update_receive_queue(self):
    while not self.result_queue.empty():
      data = self.result_queue.get(block=False)
      assert (data["unique_key"] not in self.received_data)
      if data["unique_key"] in self.ack_not_expected:
        self.logger.log(self.logger.LL_DEBUG, "[hwcp] _update_receive_queue: dropping unique_key={} - ack not expected".format(data["unique_key"]))
        self.ack_not_expected.remove(data["unique_key"])
      else:
        self.received_data[data["unique_key"]] = data

  def send_command(self, cmd, expect_ack):
    self.logger.log(self.logger.LL_DEBUG, "[hwcp] send_command: {} expect_ack={}".format(cmd, expect_ack))
    if not expect_ack:
      self.ack_not_expected.append(cmd["unique_key"])
    self.request_queue.put(cmd, block=False)
    return cmd["unique_key"]

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

  def update(self):
    self._update_receive_queue()

  def shutdown(self):
    self.logger.log(self.logger.LL_INFO, "[hwcp] shutdown")
    assert (self.hwc_process.is_alive())
    self.send_command(hw_command.gen_stop(), False)
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
    return self._send_data(packed_data, False)

  def send_enables(self, chan_enable, pdw_enable, status_enable):
    self.logger.log(self.logger.LL_DEBUG, "[hw_cfg] send_enables: {} {} {}".format(chan_enable, pdw_enable, status_enable))
    packed_data = PACKED_ESM_CONFIG_CONTROL.pack(ESM_CONTROL_MAGIC_NUM,
                                              self.seq_num,
                                              ESM_MODULE_ID_CONTROL, ESM_CONTROL_MESSAGE_TYPE_ENABLE,
                                              status_enable, pdw_enable, chan_enable, 0)
    self.seq_num += 1
    return self._send_data(packed_data, False)

  def send_module_data(self, mod_id, msg_type, data, expect_ack):
    self.logger.log(self.logger.LL_DEBUG, "[hw_cfg] send_module_data: mod_id={} msg_type={} len(data)={}".format(mod_id, msg_type, len(data)))
    packed_header = PACKED_ESM_CONFIG_HEADER.pack(ESM_CONTROL_MAGIC_NUM, self.seq_num, msg_type, mod_id)
    self.seq_num += 1
    combined_data = packed_header + data
    return self._send_data(combined_data, expect_ack)

  def _send_data(self, data, expect_ack):
    num_words = (len(data) + 3) // 4
    if num_words % 2 != 0:
      raise RuntimeError("Odd-length transfer attempted... this probably won't work.")
    cmd = hw_command.gen_write_dma(self.hwcp.get_next_unique_key(), data)
    return self.hwcp.send_command(cmd, expect_ack)


class pluto_esm_hw_interface:
  def __init__(self, logger, pluto_uri):
    self.logger = logger

    #todo: iio info
    self.hwcp             = pluto_esm_hw_command_processor(pluto_uri, self.logger)
    self.hwdr             = pluto_esm_hw_dma_reader.pluto_esm_hw_dma_reader(pluto_uri, self.logger)
    self.hw_cfg           = pluto_esm_hw_config(self.logger, self.hwcp)
    self.status_reporter  = pluto_esm_status_reporter.pluto_esm_status_reporter(self.logger, self.hwdr.output_data_status)

    self.logger.log(self.logger.LL_INFO, "[hwi] init done, hwcp={} hwdr={}".format(self.hwcp, self.hwdr))

    self.fast_lock_cal_pending = []

    self.initial_ad9361_setup()
    self.hw_cfg.send_reset()
    self.hw_cfg.send_enables(3, 3, 1)

  def initial_ad9361_setup(self):
    attributes_phy      = [("bb_dc_offset_tracking_en",  "1"),
                           ("filter_fir_en",             "0"),
                           ("gain_control_mode",         "manual"),
                           ("hardwaregain",              "30"),
                           ("quadrature_tracking_en",    "1"),
                           ("rf_bandwidth",              "56000000"),
                           ("rf_dc_offset_tracking_en",  "1"),
                           ("bb_dc_offset_tracking_en",  "1"),
                           ("sampling_frequency",        "61440000")]
    attributes_dev_dbg  = [("adi,rx-fastlock-pincontrol-enable", "1")]

    for entry in attributes_phy:
      cmd = hw_command.gen_write_attr_phy(self.hwcp.get_next_unique_key(), entry[0], entry[1])
      self.hwcp.send_command(cmd, False)

    for entry in attributes_dev_dbg:
      cmd = hw_command.gen_write_attr_dbg(self.hwcp.get_next_unique_key(), entry[0], entry[1])
      self.hwcp.send_command(cmd, False)

  #TODO: move this to the sequencer? at least move the cal pending stuff
  def send_fast_lock_cal_cmd(self, frequency):
    self.logger.log(self.logger.LL_INFO, "[hwi] send_fast_lock_cal_cmd: freq={}".format(frequency))

    cmd = []
    cmd.append(hw_command.gen_write_attr_rx_lo(self.hwcp.get_next_unique_key(), "frequency", str(int(frequency * 1e6))))
    cmd.append(hw_command.gen_write_attr_rx_lo(self.hwcp.get_next_unique_key(), "fastlock_store", "0"))
    cmd.append(hw_command.gen_read_attr_rx_lo(self.hwcp.get_next_unique_key(), "fastlock_save"))

    self.fast_lock_cal_pending.append({"freq": frequency, "keys": [c["unique_key"] for c in cmd]})

    for entry in cmd:
      self.hwcp.send_command(entry, True)

  def check_fast_lock_cal_results(self):
    assert (len(self.fast_lock_cal_pending) > 0)
    cmd_result = self.hwcp.try_get_result(self.fast_lock_cal_pending[0]["keys"][0])

    if cmd_result is not None:
      finished_key = self.fast_lock_cal_pending[0]["keys"].pop(0)
      assert (cmd_result["unique_key"] == finished_key)
      if len(self.fast_lock_cal_pending[0]["keys"]) == 0:
        freq = self.fast_lock_cal_pending[0]["freq"]
        self.fast_lock_cal_pending.pop(0)
        return {"freq": freq, "data": cmd_result["data"]}

    return None

  def send_fast_lock_profile(self, profile_index, profile_data):
    modified_data = "{} {}".format(profile_index, profile_data.split(" ")[1])
    cmd = hw_command.gen_write_attr_rx_lo(self.hwcp.get_next_unique_key(), "fastlock_load", modified_data)
    return self.hwcp.send_command(cmd, True)

  def send_fastlock_recall(self, value):
    cmd = hw_command.gen_write_attr_rx_lo(self.hwcp.get_next_unique_key(), "fastlock_recall", value)
    return self.hwcp.send_command(cmd, True)

  def update(self):
    self.hwcp.update()
    self.hwdr.update()
    self.status_reporter.update()

  def shutdown(self):
    self.hw_cfg.send_reset()
    self.logger.log(self.logger.LL_INFO, "sleeping for 3 seconds before shutdown")
    time.sleep(3.0)
    self.hwcp.shutdown()
    self.hwdr.shutdown()