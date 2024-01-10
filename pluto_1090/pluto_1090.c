#include <getopt.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include <signal.h>
#include <stdio.h>
#include <iio.h>
#include <unistd.h>
#include <errno.h>
#include <assert.h>

#define IIO_ENSURE(expr) { \
  if (!(expr)) { \
    (void) fprintf(stderr, "assertion failed (%s:%d)\n", __FILE__, __LINE__); \
    (void) abort(); \
  } \
}

#define DMA_WORD_BYTE_SIZE 4
#define D2H_DEVICE_NAME "iio:device4"
#define H2D_DEVICE_NAME "iio:device5"

typedef struct {
  uint32_t magic_num;
  uint8_t reset;
  uint8_t enable;
  uint16_t padding;
} adsb_config_t;

typedef struct {
  uint32_t magic_num;
  uint32_t sequence_num;
  uint64_t timestamp;
  uint32_t preamble_s;
  uint32_t preamble_sn;
  uint32_t message_crc;
  uint32_t message_data [4];
} adsb_report_t;

const uint32_t D2H_BUFFER_WORD_SIZE = sizeof(adsb_report_t) / DMA_WORD_BYTE_SIZE;
const uint32_t H2D_BUFFER_WORD_SIZE = sizeof(adsb_config_t) / DMA_WORD_BYTE_SIZE;

static const struct option options[] = {
  {"help",            no_argument,        0, 'h'},
  {"address",         required_argument,  0, 'a'},
  {0, 0, 0, 0},
};

static const char *options_descriptions[] = {
  "Show this help and quit.",
  "IIO device address.",
};

static void usage(char *argv[])
{
  unsigned int i;

  printf("Usage:\n\t%s [-s <size>] <iio_device>\n\nOptions:\n", argv[0]);
  for (i = 0; options[i].name; i++)
  {
    printf("\t-%c, --%s\n\t\t\t%s\n", options[i].val, options[i].name, options_descriptions[i]);
  }
}

/* IIO structs required for streaming */
static struct iio_context*  ctx             = NULL;
static struct iio_channel*  dma_chan_h2d    = NULL;
static struct iio_channel*  dma_chan_d2h    = NULL;
static struct iio_buffer*   dma_buffer_h2d  = NULL;
static struct iio_buffer*   dma_buffer_d2h  = NULL;

static bool stop = false;

/* cleanup and exit */
void shutdown()
{
  printf("* Destroying buffers\n");
  if (dma_buffer_h2d)
    iio_buffer_destroy(dma_buffer_h2d);
  if (dma_buffer_d2h)
    iio_buffer_destroy(dma_buffer_d2h);

  printf("* Disabling streaming channels\n");
  if (dma_chan_h2d)
    iio_channel_disable(dma_chan_h2d);
  if (dma_chan_d2h)
    iio_channel_disable(dma_chan_d2h);

  printf("* Destroying context\n");
  if (ctx)
    iio_context_destroy(ctx);

  exit(0);
}

static void handle_sig(int sig)
{
  printf("Waiting for process to finish... Got signal %d\n", sig);
  stop = true;
}

void print_buffer(const char *pref, const struct iio_channel* dma_chan, const struct iio_buffer* dma_buffer)
{
  if ((pref == NULL) || (dma_buffer == NULL))
  {
    return;
    }

  void *p_dat     = NULL;
  void *p_end     = iio_buffer_end(dma_buffer);
  ptrdiff_t p_inc = iio_buffer_step(dma_buffer);

  printf("%s", pref);
  for (p_dat = iio_buffer_first(dma_buffer, dma_chan); p_dat < p_end; p_dat += p_inc)
  {
    printf("0x%08jx ", *(uint64_t *)p_dat);
  }
  printf("\n");
}

void send_config()
{
  void *p_dat = NULL;
  int n_bytes = 0;
  char err_str[512];

  adsb_config_t config_data [2];
  config_data[0].magic_num = 0xAD5B0101;
  config_data[0].reset     = 1;
  config_data[0].enable    = 0;
  config_data[1].magic_num = 0xAD5B0101;
  config_data[1].reset     = 0;
  config_data[1].enable    = 1;

  for (int i = 0; i < 2; i++)
  {
    p_dat = iio_buffer_first(dma_buffer_h2d, dma_chan_h2d);
    if (!p_dat)
    {
      fprintf(stderr, "send_config: failed to get h2d buffer\n");
      shutdown();
    }
    memcpy(p_dat, &(config_data[i]), sizeof(config_data[i]));

    n_bytes = iio_buffer_push(dma_buffer_h2d);
    if (n_bytes < 0)
    {
      iio_strerror(-n_bytes, err_str, sizeof(err_str));
      printf("* Error pushing buffer %d: %s\n", n_bytes, err_str);
      if (n_bytes == -ETIMEDOUT)
      {
        printf("send_config: Ensure that transmit buffer is getting emptied. Run RX first if in loopback.");
      }
      shutdown();
    }
  }
}

/* simple configuration and streaming */
int main (int argc, char **argv)
{
  char err_str[512];
  int n_bytes = 0;
  void *p_dat = NULL;
  void *p_end = NULL;
  ptrdiff_t p_inc = 0;
  uint64_t n = 0;
  char sbuf[16];

  struct iio_device* dev_h2d = NULL;
  struct iio_device* dev_d2h = NULL;

  char* device_addr = 0;

  unsigned int i = 0;
  bool device_is_tx = false;
  bool timeout = false;
  int option_index = 0;
  int arg_index = 0;
  char unit;
  int ret = 0;

  while ((i = getopt_long(argc, argv, "a:h", options, &option_index)) != -1)
  {
    arg_index++;
    switch (i)
    {
      case 'a':
        device_addr = optarg;
        break;

      case 'h':
      default:
        usage(argv);
        return EXIT_SUCCESS;
    }
  }

  if (arg_index + 1 >= argc)
  {
    fprintf(stderr, "Incorrect number of arguments.\n\n");
    usage(argv);
    return EXIT_FAILURE;
  }

  if (device_addr)
  {
    printf("Connecting to %s\n", device_addr);
  }
  else
  {
    fprintf(stderr, "Device address required.\n");
    return EXIT_FAILURE;
  }

  // Listen to ctrl+c and assert
  signal(SIGINT, handle_sig);

  IIO_ENSURE((ctx = iio_create_context_from_uri(device_addr)) && "No context");
  IIO_ENSURE(iio_context_get_devices_count(ctx) > 0 && "No devices");
  IIO_ENSURE((dev_d2h = iio_context_find_device(ctx, D2H_DEVICE_NAME)) && "No D2H streaming device found");
  IIO_ENSURE((dev_h2d = iio_context_find_device(ctx, H2D_DEVICE_NAME)) && "No H2D streaming device found");

  //IIO_ENSURE(iio_device_get_channels_count(dev) == 1 && "No channels");
  IIO_ENSURE((dma_chan_d2h = iio_device_get_channel(dev_d2h, 0)) && "No D2H channel");
  IIO_ENSURE((dma_chan_h2d = iio_device_get_channel(dev_h2d, 0)) && "No H2D channel");
  IIO_ENSURE(iio_channel_is_scan_element(dma_chan_d2h) && "No D2H streaming capabilities");
  IIO_ENSURE(iio_channel_is_scan_element(dma_chan_h2d) && "No H2D streaming capabilities");

  iio_channel_enable(dma_chan_d2h);
  iio_channel_enable(dma_chan_h2d);
  iio_context_set_timeout(ctx, 1000);

  IIO_ENSURE((dma_buffer_d2h = iio_device_create_buffer(dev_d2h, D2H_BUFFER_WORD_SIZE, false)) && "Failed to create D2H buffer");
  IIO_ENSURE((dma_buffer_h2d = iio_device_create_buffer(dev_h2d, H2D_BUFFER_WORD_SIZE, false)) && "Failed to create H2D buffer");

  printf("Performing data transfer. Ctrl + c to terminate.\n");

  IIO_ENSURE(iio_channel_is_output(dma_chan_h2d) && "H2D expected to be an output channel");

  send_config(dma_chan_h2d, dma_buffer_h2d);

  while (!stop)
  {
    n_bytes = iio_buffer_refill(dma_buffer_d2h);
    if (n_bytes < 0)
    {
      iio_strerror(-n_bytes, err_str, sizeof(err_str));
      printf("* Error refilling buffer %d: %s\n", n_bytes, err_str);
      if (n_bytes == -ETIMEDOUT)
      {
        printf("* Ensure that receive buffer is getting filled in PL. Run TX if in loopback.");
        if (!timeout)
          timeout = true;

        continue;
      }

      shutdown();
      break;
    }

    if (timeout)
      timeout = false;

    (void)snprintf(sbuf, sizeof(sbuf), "$ RX (%d): ", n_bytes);
    print_buffer(sbuf, dma_chan_d2h, dma_buffer_d2h);
  }

  shutdown();

  return 0;
}
