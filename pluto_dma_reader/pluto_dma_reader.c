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
#include <arpa/inet.h>

#define IIO_ENSURE(expr) { \
  if (!(expr)) { \
    (void) fprintf(stderr, "assertion failed (%s:%d)\n", __FILE__, __LINE__); \
    (void) abort(); \
  } \
}

#define DMA_WORD_BYTE_SIZE        4
#define D2H_BUFFER_WORD_SIZE_MAX  128
#define DEVICE_NAME_D2H           "axi-iio-dma-d2h"

#define UDP_PORT 50055

#pragma pack(push, 1)
typedef struct {
  uint32_t seq_num;
  uint32_t data[D2H_BUFFER_WORD_SIZE_MAX];
} dma_packet_t;
#pragma pack(pop)

static const struct option options[] = {
  {"help",            no_argument,        0, 'h'},
  {"pluto_addr",      required_argument,  0, 'p'},
  {"client_addr",     required_argument,  0, 'c'},
  {"buffer_size",     required_argument,  0, 'b'},
  {0, 0, 0, 0},
};

static const char *options_descriptions[] = {
  "Show this help and quit.",
  "Pluto IIO device address.",
  "Client IP address.",
  "DMA buffer size."
};

//todo: cleanup
static void usage(char *argv[])
{
  unsigned int i;

  printf("Usage:\n\t%s \n\nOptions:\n", argv[0]);
  for (i = 0; options[i].name; i++)
  {
    printf("\t-%c, --%s\n\t\t\t%s\n", options[i].val, options[i].name, options_descriptions[i]);
  }
}

/* IIO structs required for streaming */
static struct iio_context*  ctx               = NULL;
static struct iio_channel*  chan_dma_d2h      = NULL;
static struct iio_buffer*   dma_buffer_d2h    = NULL;
int                         socket_desc       = 0;
struct sockaddr_in          client_sockaddr   = {0};
uint32_t                    dma_seq_num       = 0;
uint32_t                    dma_buffer_size   = 0;
uint32_t                    dma_packet_size   = 0;

static bool stop = false;

/* cleanup and exit */
void app_shutdown()
{
  printf("* Destroying buffers\n");
  if (dma_buffer_d2h)
    iio_buffer_destroy(dma_buffer_d2h);

  printf("* Disabling streaming channels\n");
  if (chan_dma_d2h)
    iio_channel_disable(chan_dma_d2h);

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

bool process_buffer()
{
  if ((dma_buffer_d2h == NULL) || (chan_dma_d2h == NULL))
  {
    return -1;
  }

  void* p_data = iio_buffer_first(dma_buffer_d2h, chan_dma_d2h);
  void* p_end  = iio_buffer_end(dma_buffer_d2h);
  if ((p_data == NULL) || (p_data == p_end))
  {
    return -2;
  }

  dma_packet_t packet;
  packet.seq_num = dma_seq_num;
  dma_seq_num++;
  memcpy((void*)&packet.data, p_data, dma_buffer_size * DMA_WORD_BYTE_SIZE);

  if (sendto(socket_desc, &packet, dma_packet_size, 0, (struct sockaddr*)&client_sockaddr, sizeof(client_sockaddr)) < 0)
  {
    return -3;
  }

  return 0;
}

/* simple configuration and streaming */
int main (int argc, char **argv)
{
  char err_str[512];
  int n_bytes = 0;
  struct iio_device* dev_d2h = NULL;
  char* device_addr = 0;
  char* client_addr = 0;
  char* buffer_size = 0;
  int i = 0;
  bool timeout = false;
  int option_index = 0;
  int arg_index = 0;

  while ((i = getopt_long(argc, argv, "p:c:b:h", options, &option_index)) != -1)
  {
    arg_index++;
    switch (i)
    {
      case 'p':
        device_addr = optarg;
        break;

      case 'c':
        client_addr = optarg;
        break;

      case 'b':
        buffer_size = optarg;
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
    printf("Connecting to Pluto:%s, forwarding to client:%s:%d\n", device_addr, client_addr, UDP_PORT);
  }
  else
  {
    fprintf(stderr, "Device address required.\n");
    return EXIT_FAILURE;
  }

  if (buffer_size)
  {
    dma_buffer_size = atoi(buffer_size);
    dma_packet_size = dma_buffer_size*4 + 4;
    if ((dma_buffer_size != 64) && (dma_buffer_size != 128))
    {
      fprintf(stderr, "DMA buffer size must be 64 or 128.\n");
      return EXIT_FAILURE;
    }
    else
    {
      printf("DMA buffer size: %u\n", dma_buffer_size);
    }
  }
  else
  {
    fprintf(stderr, "DMA buffer size required.\n");
    return EXIT_FAILURE;
  }

  // Listen to ctrl+c and assert
  signal(SIGINT, handle_sig);

  socket_desc = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
  if(socket_desc < 0)
  {
    printf("Error while creating socket\n");
    return -1;
  }

  dma_seq_num = 0;

  client_sockaddr.sin_family = AF_INET;
  client_sockaddr.sin_port = htons(UDP_PORT);
  client_sockaddr.sin_addr.s_addr = inet_addr(client_addr);

  IIO_ENSURE((ctx = iio_create_context_from_uri(device_addr))                   && "No context");
  IIO_ENSURE(iio_context_get_devices_count(ctx) > 0                             && "No devices");
  IIO_ENSURE((dev_d2h       = iio_context_find_device(ctx, DEVICE_NAME_D2H))    && "No D2H streaming device found");
  IIO_ENSURE((chan_dma_d2h  = iio_device_get_channel(dev_d2h, 0))               && "No D2H channel");
  IIO_ENSURE(iio_channel_is_scan_element(chan_dma_d2h)                          && "No D2H streaming capabilities");

  iio_device_set_kernel_buffers_count(dev_d2h, 64);
  iio_channel_enable(chan_dma_d2h);
  iio_context_set_timeout(ctx, 1000);

  IIO_ENSURE((dma_buffer_d2h = iio_device_create_buffer(dev_d2h, dma_buffer_size, false)) && "Failed to create D2H buffer");

  while (!stop)
  {
    n_bytes = iio_buffer_refill(dma_buffer_d2h);
    if (n_bytes < 0)
    {
      iio_strerror(-n_bytes, err_str, sizeof(err_str));
      printf("* Error refilling buffer %d: %s\n", n_bytes, err_str);
      if (n_bytes == -ETIMEDOUT)
      {
        printf("DMA read timeout\n");
        if (!timeout)
          timeout = true;

        continue;
      }

      app_shutdown();
      break;
    }


    if (timeout)
      timeout = false;

    //(void)snprintf(sbuf, sizeof(sbuf), "Received %d bytes", n_bytes);
    //printf("Received %d bytes\n", n_bytes);
    if (n_bytes > 0)
    {
      int error = process_buffer();
      if (error)
      {
        printf("process_buffer failed: %d\n.", error);
        break;
      }
    }
  }

  app_shutdown();

  return 0;
}
