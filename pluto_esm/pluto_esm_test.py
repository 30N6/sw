import sys
import time
import iio
import numpy as np
#import pygame
#from PIL import Image
import iio_info
import esm_config
import esm_dwell_controller
import esm_reader

config = []

def main():
  global config

  context = iio.Context("ip:192.168.3.100")
  info = iio_info.iio_info(context)
  info.print_info(False)

  dev_d2h     = context.find_device("axi-iio-dma-d2h")
  dev_h2d     = context.find_device("axi-iio-dma-h2d")
  dev_ad9361  = context.find_device("ad9361-phy")

  chan_dma_d2h      = dev_d2h.find_channel("voltage0", False)
  chan_dma_h2d      = dev_h2d.find_channel("voltage0", True)
  chan_ad9361_phy   = dev_ad9361.find_channel("voltage0", False)
  chan_ad9361_rx_lo = dev_ad9361.find_channel("altvoltage0", True)

  print(dev_d2h)
  print(dev_h2d)
  print(dev_ad9361)
  print(chan_dma_d2h)
  print(chan_dma_h2d)
  print(chan_ad9361_phy)
  print(chan_ad9361_rx_lo)

  chan_dma_h2d.enabled = True
  chan_dma_d2h.enabled = True

  context.set_timeout(1000)

  config            = esm_config.esm_config(chan_dma_h2d)
  #TODO: pull out buffer
  #dwell_controller  = esm_dwell_controller.esm_dwell_controller(chan_dma_h2d)
  reader            = esm_reader.esm_reader(chan_dma_d2h)


  config.send_reset()
  config.send_enables(3, 3, 1)

  while True:
    reader.read()
    #time.sleep(0)

if __name__ == "__main__":
  try:
    main()
  except KeyboardInterrupt:
    print("interrupted: {}".format(config))
    config.send_reset()
    time.sleep(0)
    sys.exit(0)
