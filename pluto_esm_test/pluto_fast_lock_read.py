import sys
import time
import iio
import numpy as np
import iio_info

config = []

def main():
  global config

  context = iio.Context("ip:192.168.3.100")
  info = iio_info.iio_info(context)
  info.print_info(True)

  dev_d2h     = context.find_device("axi-iio-dma-d2h")
  dev_h2d     = context.find_device("axi-iio-dma-h2d")
  dev_ad9361  = context.find_device("ad9361-phy")

  chan_dma_d2h      = dev_d2h.find_channel("voltage0", False)
  chan_dma_h2d      = dev_h2d.find_channel("voltage0", True)
  chan_ad9361_phy   = dev_ad9361.find_channel("voltage0", False)
  chan_ad9361_rx_lo = dev_ad9361.find_channel("altvoltage0", True)

  while True:
    print(chan_ad9361_rx_lo.attrs["frequency"].value)
    time.sleep(0.01)

if __name__ == "__main__":
  try:
    main()
  except KeyboardInterrupt:
    print("interrupted: {}".format(config))
    time.sleep(0)
    sys.exit(0)
