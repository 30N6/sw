import numpy as np
#import pygame

def main():
  dwell_data_channel_peak = np.savetxt("./dwell_data_channel_peak.txt", self.spectrogram.dwell_data_channel_peak, "%u")
  dwell_data_channel_accum = np.savetxt("./dwell_data_channel_accum.txt", self.spectrogram.dwell_data_channel_accum, "%u")
  dwell_data_channel_duration = np.savetxt("./dwell_data_channel_duration.txt", self.spectrogram.dwell_data_channel_duration, "%u")



if __name__ == "__main__":
  try:
    main()
  except KeyboardInterrupt:
    print("interrupted: {}".format(config))
    time.sleep(0)
    sys.exit(0)
