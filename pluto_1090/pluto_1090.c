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
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <netdb.h>

#define IIO_ENSURE(expr) { \
  if (!(expr)) { \
    (void) fprintf(stderr, "assertion failed (%s:%d)\n", __FILE__, __LINE__); \
    (void) abort(); \
  } \
}
#define IIO_CHECK_WRITE_N(expr) { \
  if ((expr) < 0) { \
    (void) fprintf(stderr, "assertion failed (%s:%d) - expr=%d\n", __FILE__, __LINE__, (expr)); \
    (void) abort(); \
  } \
}
#define IIO_CHECK_WRITE_S(expr) { \
  if ((expr) < 0) { \
    (void) fprintf(stderr, "assertion failed (%s:%d) - expr=%ld\n", __FILE__, __LINE__, (expr)); \
    (void) abort(); \
  } \
}


#define MHZ(x) ((long long)(x*1000000.0 + .5))
#define GHZ(x) ((long long)(x*1000000000.0 + .5))

#define DMA_WORD_BYTE_SIZE  4
#define DEVICE_NAME_D2H     "axi-iio-dma-d2h"
#define DEVICE_NAME_H2D     "axi-iio-dma-h2d"
#define DEVICE_NAME_AD9361  "ad9361-phy"

#pragma pack(push, 1)
typedef struct {
  uint32_t magic_num;
  uint8_t reset;
  uint8_t enable;
  uint8_t crc_filter;
  uint8_t preamble_s_threshold;
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
#pragma pack(pop)

const uint32_t D2H_BUFFER_WORD_SIZE = sizeof(adsb_report_t) / DMA_WORD_BYTE_SIZE;
const uint32_t H2D_BUFFER_WORD_SIZE = sizeof(adsb_config_t) / DMA_WORD_BYTE_SIZE;

typedef struct {
    long long   rf_bandwidth_hz;
    long long   sampling_frequency_hz;
    long long   lo_hz;
    long long   hw_gain_db;
    bool        filter_fir_en;
    bool        quadrature_tracking_en;
    bool        bb_dc_offset_tracking_en;
    bool        rf_dc_offset_tracking_en;
    const char* agc_mode;
    const char* rf_port;
} adc_config;

static const struct option options[] = {
  {"help",            no_argument,        0, 'h'},
  {"pluto_addr",      required_argument,  0, 'p'},
  {"dump1090_addr",   required_argument,  0, 'd'},
  {0, 0, 0, 0},
};

static const char *options_descriptions[] = {
  "Show this help and quit.",
  "Pluto IIO device address.",
  "dump1090 address.",
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
static struct iio_context*  ctx               = NULL;
static struct iio_channel*  chan_dma_h2d      = NULL;
static struct iio_channel*  chan_dma_d2h      = NULL;
static struct iio_channel*  chan_ad9361_phy   = NULL;
static struct iio_channel*  chan_ad9361_rx_lo = NULL;
static struct iio_buffer*   dma_buffer_h2d    = NULL;
static struct iio_buffer*   dma_buffer_d2h    = NULL;

static int sockfd_dump1090 = -1;
static bool stop = false;

/* cleanup and exit */
void app_shutdown()
{
  printf("* Destroying buffers\n");
  if (dma_buffer_h2d)
    iio_buffer_destroy(dma_buffer_h2d);
  if (dma_buffer_d2h)
    iio_buffer_destroy(dma_buffer_d2h);

  printf("* Disabling streaming channels\n");
  if (chan_dma_h2d)
    iio_channel_disable(chan_dma_h2d);
  if (chan_dma_d2h)
    iio_channel_disable(chan_dma_d2h);

  printf("* Destroying context\n");
  if (ctx)
    iio_context_destroy(ctx);

  printf("* Closing dump1090 socket\n");
  if(sockfd_dump1090)
  {
    close(sockfd_dump1090);
  }

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
    printf("%08x ", *(uint32_t *)p_dat);
  }
  printf("\n");
}

void process_buffer(const char *pref, const struct iio_channel* dma_chan, const struct iio_buffer* dma_buffer)
{
  const adsb_report_t* report = (const adsb_report_t*)iio_buffer_first(dma_buffer, dma_chan);
  printf("%s", pref);
  printf("magic=%08X  seq=%08d  timestamp=%012ld  preamble=%4d/%4d SSNR=%3.1f crc=%d  msg=%08X %08X %08X %08X",
    report->magic_num, report->sequence_num, report->timestamp, report->preamble_s, report->preamble_sn, (double)report->preamble_s / (double)report->preamble_sn,
    report->message_crc, report->message_data[0], report->message_data[1], report->message_data[2], report->message_data[3]);

  if(sockfd_dump1090)
  {
    char buffer[64];
    sprintf(buffer, "*%08X%08X%08X%04X;\n", report->message_data[0], report->message_data[1], report->message_data[2], report->message_data[3] >> 16);
    printf(" -- buf=%s", buffer);
    write(sockfd_dump1090, buffer, strlen(buffer));
  }
  else
  {
    printf("\n");
  }
}

void send_adc_config(const adc_config* config)
{
  IIO_CHECK_WRITE_N(iio_channel_attr_write_longlong(chan_ad9361_rx_lo, "frequency",                config->lo_hz));
  IIO_CHECK_WRITE_N(iio_channel_attr_write_longlong(chan_ad9361_phy,   "rf_bandwidth",             config->rf_bandwidth_hz));
  IIO_CHECK_WRITE_N(iio_channel_attr_write_longlong(chan_ad9361_phy,   "sampling_frequency",       config->sampling_frequency_hz));
  IIO_CHECK_WRITE_N(iio_channel_attr_write_longlong(chan_ad9361_phy,   "hardwaregain",             config->hw_gain_db));
  IIO_CHECK_WRITE_N(iio_channel_attr_write_bool(chan_ad9361_phy,       "quadrature_tracking_en",   config->quadrature_tracking_en));
  IIO_CHECK_WRITE_N(iio_channel_attr_write_bool(chan_ad9361_phy,       "bb_dc_offset_tracking_en", config->bb_dc_offset_tracking_en));
  IIO_CHECK_WRITE_N(iio_channel_attr_write_bool(chan_ad9361_phy,       "rf_dc_offset_tracking_en", config->rf_dc_offset_tracking_en));
  IIO_CHECK_WRITE_N(iio_channel_attr_write_bool(chan_ad9361_phy,       "filter_fir_en",            config->filter_fir_en));
  IIO_CHECK_WRITE_S(iio_channel_attr_write(chan_ad9361_phy,            "gain_control_mode",        config->agc_mode));
  IIO_CHECK_WRITE_S(iio_channel_attr_write(chan_ad9361_phy,            "rf_port_select",           config->rf_port));
}

void send_adsb_config()
{
  void *p_dat = NULL;
  int n_bytes = 0;
  char err_str[512];

  adsb_config_t config_data [2];
  config_data[0].magic_num            = 0xAD5B0101;
  config_data[0].reset                = 1;
  config_data[0].enable               = 0;
  config_data[1].magic_num            = 0xAD5B0101;
  config_data[1].reset                = 0;
  config_data[1].enable               = 1;
  config_data[1].crc_filter           = 1;
  config_data[1].preamble_s_threshold = 5;

  for (int i = 0; i < 2; i++)
  {
    p_dat = iio_buffer_first(dma_buffer_h2d, chan_dma_h2d);
    if (!p_dat)
    {
      fprintf(stderr, "send_adsb_config: failed to get h2d buffer\n");
      app_shutdown();
    }
    memcpy(p_dat, &(config_data[i]), sizeof(config_data[i]));

    n_bytes = iio_buffer_push(dma_buffer_h2d);
    if (n_bytes < 0)
    {
      iio_strerror(-n_bytes, err_str, sizeof(err_str));
      printf("* Error pushing buffer %d: %s\n", n_bytes, err_str);
      if (n_bytes == -ETIMEDOUT)
      {
        printf("send_adsb_config: Ensure that transmit buffer is getting emptied. Run RX first if in loopback.");
      }
      app_shutdown();
    }
    else
    {
      printf("send_adsb_config: %d bytes sent\n", n_bytes);
    }
    usleep(1000);
  }
}

void init_dump1090(const char* dump1090_addr)
{
    int portno = 30001;
    int n;
    struct sockaddr_in serv_addr;
    struct hostent *server;

    sockfd_dump1090 = socket(AF_INET, SOCK_STREAM, 0);
    if (sockfd_dump1090 < 0)
    {
      fprintf(stderr, "init_dump1090: ERROR opening socket\n");
      return;
    }

    server = gethostbyname(dump1090_addr);
    if (server == NULL)
    {
        fprintf(stderr,"init_dump1090: ERROR, no such host\n");
        close(sockfd_dump1090);
        sockfd_dump1090 = -1;
        return;
    }

    bzero((char *) &serv_addr, sizeof(serv_addr));
    serv_addr.sin_family = AF_INET;
    bcopy((char *)server->h_addr, (char *)&serv_addr.sin_addr.s_addr, server->h_length);
    serv_addr.sin_port = htons(portno);

    if (connect(sockfd_dump1090, (struct sockaddr *) &serv_addr, sizeof(serv_addr)) < 0)
    {
      fprintf(stderr, "init_dump1090: ERROR connecting");
      close(sockfd_dump1090);
      sockfd_dump1090 = -1;
      return;
    }

    printf("init_dump1090: fd=%d\n", sockfd_dump1090);

    /*printf("Please enter the message: ");
    bzero(buffer,256);
    fgets(buffer,255,stdin);
    n = write(sockfd,buffer,strlen(buffer));
    if (n < 0)
         error("ERROR writing to socket");
    bzero(buffer,256);
    n = read(sockfd,buffer,255);
    if (n < 0)
         error("ERROR reading from socket");
    printf("%s\n",buffer);
    close(sockfd);
    return 0;*/
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
  struct iio_device* dev_ad9361 = NULL;

  char* device_addr = 0;
  char* dump1090_addr = 0;

  unsigned int i = 0;
  bool device_is_tx = false;
  bool timeout = false;
  int option_index = 0;
  int arg_index = 0;
  char unit;
  int ret = 0;

  while ((i = getopt_long(argc, argv, "p:d:h", options, &option_index)) != -1)
  {
    arg_index++;
    switch (i)
    {
      case 'p':
        device_addr = optarg;
        break;

      case 'd':
        dump1090_addr = optarg;
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
    printf("Connecting to Pluto: %s\n", device_addr);
  }
  else
  {
    fprintf(stderr, "Device address required.\n");
    return EXIT_FAILURE;
  }

  if (dump1090_addr)
  {
    printf("Connecting to dump1090: %s\n", dump1090_addr);
    init_dump1090(dump1090_addr);
  }
  else
  {
    printf("dump1090 address not specified -- skipping\n");
  }

  // Listen to ctrl+c and assert
  signal(SIGINT, handle_sig);

  IIO_ENSURE((ctx = iio_create_context_from_uri(device_addr)) && "No context");
  IIO_ENSURE(iio_context_get_devices_count(ctx) > 0 && "No devices");
  IIO_ENSURE((dev_d2h     = iio_context_find_device(ctx, DEVICE_NAME_D2H))    && "No D2H streaming device found");
  IIO_ENSURE((dev_h2d     = iio_context_find_device(ctx, DEVICE_NAME_H2D))    && "No H2D streaming device found");
  IIO_ENSURE((dev_ad9361  = iio_context_find_device(ctx, DEVICE_NAME_AD9361)) && "No AD9361 device found");

  //IIO_ENSURE(iio_device_get_channels_count(dev) == 1 && "No channels");
  IIO_ENSURE((chan_dma_d2h      = iio_device_get_channel(dev_d2h, 0))                         && "No D2H channel");
  IIO_ENSURE((chan_dma_h2d      = iio_device_get_channel(dev_h2d, 0))                         && "No H2D channel");
  IIO_ENSURE((chan_ad9361_phy   = iio_device_find_channel(dev_ad9361, "voltage0",     false)) && "No ADC9361-phy channel");
  IIO_ENSURE((chan_ad9361_rx_lo = iio_device_find_channel(dev_ad9361, "altvoltage0",  true))  && "No ADC9361-rx_lo channel");

  IIO_ENSURE(iio_channel_is_scan_element(chan_dma_d2h) && "No D2H streaming capabilities");
  IIO_ENSURE(iio_channel_is_scan_element(chan_dma_h2d) && "No H2D streaming capabilities");

  iio_channel_enable(chan_dma_d2h);
  iio_channel_enable(chan_dma_h2d);
  iio_context_set_timeout(ctx, 1000);

  IIO_ENSURE((dma_buffer_d2h = iio_device_create_buffer(dev_d2h, D2H_BUFFER_WORD_SIZE, false)) && "Failed to create D2H buffer");
  IIO_ENSURE((dma_buffer_h2d = iio_device_create_buffer(dev_h2d, H2D_BUFFER_WORD_SIZE, false)) && "Failed to create H2D buffer");

  printf("Performing data transfer. Ctrl + c to terminate.\n");

  IIO_ENSURE(iio_channel_is_output(chan_dma_h2d) && "H2D expected to be an output channel");

  adc_config config;
  config.rf_bandwidth_hz          = MHZ(3.0);
  config.sampling_frequency_hz    = MHZ(8.0);
  config.lo_hz                    = MHZ(1090);
  config.hw_gain_db               = 70;
  config.filter_fir_en            = 0;
  config.quadrature_tracking_en   = 1;
  config.bb_dc_offset_tracking_en = 1;
  config.rf_dc_offset_tracking_en = 1;
  config.agc_mode                 = "manual";
  config.rf_port                  = "A_BALANCED";

  send_adc_config(&config);
  send_adsb_config(chan_dma_h2d, dma_buffer_h2d);

  while (!stop)
  {
    n_bytes = iio_buffer_refill(dma_buffer_d2h);
    if (n_bytes < 0)
    {
      iio_strerror(-n_bytes, err_str, sizeof(err_str));
      printf("* Error refilling buffer %d: %s\n", n_bytes, err_str);
      if (n_bytes == -ETIMEDOUT)
      {
        printf("* Ensure that receive buffer is getting filled in PL. Run TX if in loopback.\n");
        if (!timeout)
          timeout = true;

        continue;
      }

      app_shutdown();
      break;
    }

    if (timeout)
      timeout = false;

    (void)snprintf(sbuf, sizeof(sbuf), "$ RX (%d): ", n_bytes);
    process_buffer(sbuf, chan_dma_d2h, dma_buffer_d2h);

    usleep(10000);
  }

  app_shutdown();

  return 0;
}
