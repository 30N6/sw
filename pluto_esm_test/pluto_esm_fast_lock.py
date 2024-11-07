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

  print(dev_ad9361.debug_attrs)

  return

  for attr in chan_ad9361_rx_lo.attrs:
    print(attr)
  print("\n\n")

  freqs = range(100, 6000, 40)
  cmd_time = np.zeros(len(freqs) + 1)
  cmd_time[0] = time.time()
  for i in range(len(freqs)):
    freq = freqs[i]
    chan_ad9361_rx_lo.attrs["frequency"].value = str(int(freq * 1e6))
    chan_ad9361_rx_lo.attrs["fastlock_store"].value = str(0)
    fast_lock_data = chan_ad9361_rx_lo.attrs["fastlock_save"].value
    cmd_time[i + 1] = time.time()
    print("{:4} : {} {}".format(freq, fast_lock_data, cmd_time[i + 1] - cmd_time[i]))

  print("total time = {} max={} num_freqs={}".format(cmd_time[-1] - cmd_time[0], np.max(np.diff(cmd_time)), len(freqs)))

if __name__ == "__main__":
  try:
    main()
  except KeyboardInterrupt:
    print("interrupted: {}".format(config))
    config.send_reset()
    #config.send_enables(0, 0, 0)
    time.sleep(0)
    sys.exit(0)
