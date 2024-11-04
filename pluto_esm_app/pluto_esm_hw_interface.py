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
  def gen_write_dma_h2d(unique_key, data):
    return {"unique_key": unique_key, "command_type": hw_command.CMD_WRITE_DMA_H2D, "attr": None, "data": data}

  @staticmethod
  def gen_stop():
    return {"unique_key": 0, "command_type": hw_command.CMD_STOP, "attr": None, "data": None}


class pluto_esm_hw_command_processor_thread:
  def __init__(self, arg):
    #TODO: logging
    self.pipe               = arg["pipe"]
    self.context            = iio.Context(arg["pluto_uri"])
    self.dev_h2d            = self.context.find_device("axi-iio-dma-h2d")
    self.dev_ad9361         = self.context.find_device("ad9361-phy")
    self.chan_dma_h2d       = self.dev_h2d.find_channel("voltage0", True)
    self.chan_ad9361_phy    = self.dev_ad9361.find_channel("voltage0", False)
    self.chan_ad9361_rx_lo  = self.dev_ad9361.find_channel("altvoltage0", True)

    print("pluto_esm_hw_command_processor_thread init: pipe={} context={} dma_h2d={} phy={} rx_lo={}".format(
      self.pipe, self.context, self.chan_dma_h2d, self.chan_ad9361_phy, self.chan_ad9361_rx_lo))

  def run(self):
    running = True
    while running:
      cmd = self.pipe.recv()
      if cmd["command_type"] == hw_command.CMD_WRITE_ATTR_PHY:
        print("write attr phy start: {}".format(time.time()))
        self.chan_ad9361_phy.attrs[cmd["attr"]].value = cmd["data"]
        self.pipe.send({"unique_key": cmd["unique_key"], "data": None})
        print("write attr phy done: {}".format(time.time()))
      elif cmd["command_type"] == hw_command.CMD_WRITE_ATTR_RX_LO:
        print("write attr rx_lo start: {}".format(time.time()))
        self.chan_ad9361_rx_lo.attrs[cmd["attr"]].value = cmd["data"]
        self.pipe.send({"unique_key": cmd["unique_key"], "data": None})
        print("write attr rx_lo done: {}".format(time.time()))
      elif cmd["command_type"] == hw_command.CMD_READ_ATTR_PHY:
        pass
      elif cmd["command_type"] == hw_command.CMD_READ_ATTR_RX_LO:
        pass
      elif cmd["command_type"] == hw_command.CMD_WRITE_DMA_H2D:
        pass
      elif cmd["command_type"] == hw_command.CMD_STOP:
        running = False
      else:
        print("invalid command")
        running = False

    print("hw_cmd_proc_run exiting...")

def pluto_esm_hw_command_processor_thread_func(arg):
  print("pluto_esm_hw_command_processor_thread_func starting: arg={}".format(arg))
  thread = pluto_esm_hw_command_processor_thread(arg)
  thread.run()

class pluto_esm_hw_command_processor:
  def __init__(self, pluto_uri):
    self.unique_key = 0
    self.received_data = {}
    self.pluto_uri = pluto_uri
    self.master_pipe, slave_pipe = Pipe()

    print("starting hw commander thread")
    self.hwc_process = Process(target=pluto_esm_hw_command_processor_thread_func, args=({"pluto_uri": pluto_uri, "pipe": slave_pipe}, ))
    self.hwc_process.start()

  def update_receive_queue(self):
    while self.master_pipe.poll():
      data = self.master_pipe.recv()
      print("update_receive_queue: {}".format(data))
      assert (data["unique_key"] not in self.received_data)
      self.received_data[data["unique_key"]] = data

  def send_command(self, cmd):
    self.master_pipe.send(cmd)

  def try_get_result(self, unique_key):
    self.update_receive_queue()
    if unique_key in self.received_data:
      return self.received_data.pop(unique_key)
    else:
      return None

  def get_next_unique_key(self):
    k = self.unique_key
    self.unique_key += 1
    return k

  def shutdown(self):
    assert (self.hwc_process.is_alive())
    self.send_command(hw_command.gen_stop())
    self.hwc_process.join(1.0)
    assert (not self.hwc_process.is_alive())

class pluto_esm_hw_interface:

  def __init__(self, logger, pluto_uri):
    #TODO: logging

    #context = iio.Context(pluto_uri)
    #todo: iio info

    self.hw_cmd_proc = pluto_esm_hw_command_processor(pluto_uri)
    #TODO self.dma_reader =

  def test(self):
    for freq in range(500, 5000, 100):
      cmd = hw_command.gen_write_attr_rx_lo(self.hw_cmd_proc.get_next_unique_key(), "frequency", str(int(freq * 1e6)))
      start_time = time.time()
      print("[{}] sending command: {}".format(start_time, cmd))
      self.hw_cmd_proc.send_command(cmd)
      r = None
      while r is None:
        r = self.hw_cmd_proc.try_get_result(cmd["unique_key"])
      end_time = time.time()
      print("[{}] command complete: {} -- diff={}".format(end_time, r, end_time - start_time))

  def shutdown(self):
    self.hw_cmd_proc.shutdown()
