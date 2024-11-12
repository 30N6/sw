import numpy as np
import pygame
import turbo_colormap

def main():
  SCREEN_SIZE = (1280, 800)
  FPS = 60

  dwell_data_channel_peak     = np.loadtxt("./dwell_data_channel_peak_1.3ghz_ant.txt", dtype=np.uint32)
  dwell_data_channel_accum    = np.loadtxt("./dwell_data_channel_accum_1.3ghz_ant.txt", dtype=np.uint64)
  dwell_data_channel_duration = np.loadtxt("./dwell_data_channel_duration_1.3ghz_ant.txt", dtype=np.uint32)

  output_size = [256, 600]
  width_ratio = dwell_data_channel_peak.shape[1] / output_size[1]

  buf_avg   = np.zeros((output_size[0], output_size[1]))
  buf_peak  = np.zeros((output_size[0], output_size[1]))

  input_avg = dwell_data_channel_accum
  input_avg[:, 49::50] = 0

  input_peak = dwell_data_channel_peak
  input_peak[:, 49::50] = 0


  for output_col in range(output_size[1]):
      input_cols = range(int(output_col * width_ratio), int((output_col + 1) * width_ratio))
      buf_avg[:, output_col] = np.sum(input_avg[:, input_cols], 1)
      buf_peak[:, output_col] = np.sum(input_peak[:, input_cols], 1)

  #output_peak = normalize_db(buf_peak)
  #output_peak = normalize_sqrt(buf_peak)

  #output_data = normalize_db(buf_peak).transpose()
  output_data = normalize_sqrt(buf_avg).transpose()
  #output_data = normalize_sqrt(buf_peak).transpose()

  output_data = turbo_colormap.interpolate_color(output_data)

  output_data = output_data.repeat(2, axis=1)



  #output_peak = np.empty((norm_peak.shape[0], norm_peak.shape[1], 3), np.uint8)
  #for i in range(3):
  #  output_peak[:,:,i] = norm_peak.astype(np.uint8)

  #print(row_max_peak)
  #print(row_max_peak.size)
  #print(norm_peak.shape)
  #output_peak = np

  pygame.init()
  surface = pygame.display.set_mode(SCREEN_SIZE)
  pygame.display.set_caption("pluto_esm")
  clock = pygame.time.Clock()

  running = True
  while (running):
    for i in pygame.event.get():
      if i.type == pygame.QUIT:
        running = False

    surface.fill((0,0,0))

    rect = [16, 128, 600, 360]
    surf = pygame.surfarray.make_surface(output_data)
    surface.blit(surf, rect)


    pygame.display.flip()
    clock.tick(FPS)

def normalize_sqrt(data):
  row_max = np.max(data, 1)
  norm_data = np.empty(data.shape)
  for row in range(row_max.size):
    row_scaled = np.divide(data[row, :], row_max[row])
    row_sqrt = np.sqrt(np.sqrt(row_scaled))
    norm_data[row, :] = row_sqrt #255.0 * row_sqrt

  #print(data[0, :].astype(np.uint32))
  #print(norm_data[0, :].astype(np.uint8))

  return norm_data


def normalize_db(data):
  row_max = np.max(data, 1)
  norm_data = np.empty(data.shape)
  for row in range(row_max.size):
    row_scaled = np.divide(data[row, :], row_max[row])
    row_db = 10*np.log10(row_scaled)

    row_valid_db = row_db[~np.isinf(row_db)]
    row_min = np.min(row_valid_db) - 10
    row_adjusted = np.divide(row_db - row_min, (0 - row_min))
    row_adjusted[np.isinf(row_adjusted)] = 0

    norm_data[row, :] = 255.0 * row_adjusted

  print(data[0, :].astype(np.uint32))
  print(norm_data[0, :].astype(np.uint8))

  return norm_data.astype(np.uint8)

if __name__ == "__main__":
  try:
    main()
  except KeyboardInterrupt:
    print("interrupted: {}".format(config))
    time.sleep(0)
    sys.exit(0)
