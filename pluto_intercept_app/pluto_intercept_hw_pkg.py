import struct

PACKED_UINT8  = "B"
PACKED_UINT16 = "H"
PACKED_INT16  = "h"
PACKED_UINT32 = "I"
PACKED_INT32  = "i"
PACKED_UINT64 = "Q"

UDP_FILTER_PORT                                         = 65200

INTERCEPT_CONTROL_MAGIC_NUM                             = 0x494E5443
INTERCEPT_REPORT_MAGIC_NUM                              = 0x494E5452

INTERCEPT_MODULE_ID_CONTROL                             = 0x00
INTERCEPT_MODULE_ID_DWELL_CONTROLLER                    = 0x01
INTERCEPT_MODULE_ID_DWELL_STATS                         = 0x02
INTERCEPT_MODULE_ID_STREAM_ENCODER                      = 0x03
INTERCEPT_MODULE_ID_STATUS                              = 0x07

INTERCEPT_CONTROL_MESSAGE_TYPE_ENABLE                   = 0x00
INTERCEPT_CONTROL_MESSAGE_TYPE_DWELL_CONTROLLER_CONFIG  = 0x01
INTERCEPT_CONTROL_MESSAGE_TYPE_CHANNEL_CONFIG           = 0x02
INTERCEPT_CONTROL_MESSAGE_TYPE_STREAM_CONFIG            = 0x03

INTERCEPT_REPORT_MESSAGE_TYPE_DWELL_STATS               = 0x10
INTERCEPT_REPORT_MESSAGE_TYPE_STREAM                    = 0x20
INTERCEPT_REPORT_MESSAGE_TYPE_STATUS                    = 0x30

INTERCEPT_NUM_CHANNELS                                  = 512
INTERCEPT_NUM_STREAMS                                   = 16

INTERCEPT_DWELL_DURATION_MAX_FRAMES                     = 65535
INTERCEPT_DWELL_DURATION_MIN_FRAMES                     = 16

INTERCEPT_STREAM_TRIGGER_TYPE_NORMAL                    = 0
INTERCEPT_STREAM_TRIGGER_TYPE_COAST                     = 1
INTERCEPT_STREAM_TRIGGER_TYPE_FORCED                    = 2
INTERCEPT_STREAM_TRIGGER_TYPE_LAST                      = 3

ADC_CLOCK_FREQUENCY                                     = 61.44e6
ADC_CLOCK_PERIOD                                        = 1/61.44e6
FAST_CLOCK_PERIOD                                       = 1/(4*61.44e6)
CHANNELIZER_OVERSAMPLING                                = 2.0

CHANNELIZER_DATA_WIDTH                                  = 25
CHANNELIZER_SCALE_FACTOR                                = 1 / (2**(CHANNELIZER_DATA_WIDTH - 1))

ETH_MAC_HEADER_LENGTH                                   = 14
ETH_IPV4_HEADER_LENGTH                                  = 20
ETH_UDP_HEADER_LENGTH                                   = 8

PACKED_INTERCEPT_REPORT_COMMON_HEADER   = struct.Struct("<" + PACKED_UINT32 + PACKED_UINT32 + "xx"          + PACKED_UINT8 + PACKED_UINT8 + "xxxx")     #magic number, msg seq num, message type, module id
PACKED_INTERCEPT_CONFIG_HEADER          = struct.Struct("<" + PACKED_UINT32 + PACKED_UINT32 + PACKED_UINT16 + PACKED_UINT8 + PACKED_UINT8 + "xxxx")     #magic number, msg seq num, address, message type, module id
PACKED_INTERCEPT_CONFIG_CONTROL         = struct.Struct("<" + PACKED_UINT32 + PACKED_UINT32 + PACKED_UINT16 + PACKED_UINT8 + PACKED_UINT8 + "xxxx" +    # common header
                                                              PACKED_UINT8 + PACKED_UINT8 + PACKED_UINT8 + PACKED_UINT8 + "xxxx")                       # reset, enables x 3

PACKED_INTERCEPT_CONFIG_DWELL_CONTROL   = struct.Struct("<" + PACKED_UINT8 +                                                                            # enable
                                                              "x" +
                                                              PACKED_UINT16 +                                                                           # tag
                                                              PACKED_UINT32 +                                                                           # frequency
                                                              PACKED_UINT32 +                                                                           # window duration
                                                              "xxxx")

PACKED_INTERCEPT_CONFIG_CHANNEL_CONTROL = struct.Struct("<" + PACKED_UINT8 +                                                                            # enable
                                                              PACKED_UINT8 +                                                                            # force trigger
                                                              PACKED_UINT8 +                                                                            # force stream index
                                                              "x" +
                                                              PACKED_UINT16 +                                                                           # tag
                                                              "xx" +
                                                              PACKED_UINT32 +                                                                           # threshold_start
                                                              PACKED_UINT32 +                                                                           # threshold_continue
                                                              PACKED_UINT32 +                                                                           # coast cycles
                                                              PACKED_UINT32)                                                                            # integration cycles

PACKED_INTERCEPT_CONFIG_STREAM_CONTROL  = struct.Struct("<" + PACKED_UINT8 +                                                                            # enable
                                                              "x" +
                                                              PACKED_UINT16 +                                                                           # tag
                                                              "xxxx")

PACKED_STATUS_REPORT                    = struct.Struct("<" + PACKED_UINT32 + PACKED_UINT32 + "xx"          + PACKED_UINT8 + PACKED_UINT8 + "xxxx" +
                                                              PACKED_UINT32 + PACKED_UINT32 + PACKED_UINT32 + PACKED_UINT32 + PACKED_UINT32)

PACKED_DWELL_STATS_HEADER               = struct.Struct("<" + PACKED_UINT32 + PACKED_UINT32 + "xx"          + PACKED_UINT8 + PACKED_UINT8 + "xxxx" +    # common report header
                                                              PACKED_UINT32 + PACKED_UINT32 + PACKED_UINT16 + PACKED_UINT16 +                           # dwell data: seq num, frequency, tag, window duration
                                                              PACKED_UINT32 +                                                                           # window seq num
                                                              PACKED_UINT32 + PACKED_UINT32)                                                            # window timestamp

PACKED_DWELL_STATS_CHANNEL_ENTRY        = struct.Struct("<" + PACKED_UINT8 + "x" + PACKED_UINT16 + PACKED_UINT32 + PACKED_UINT32 + PACKED_UINT32)       # valid, index, accum0, accum1, max

PACKED_STREAM_HEADER                    = struct.Struct("<" + PACKED_UINT32 + PACKED_UINT32 + "xx"          + PACKED_UINT8 + PACKED_UINT8 + "xxxx" +    # common report header
                                                              PACKED_UINT32 + PACKED_UINT32 + PACKED_UINT16 + PACKED_UINT16 +                           # dwell data: seq num, frequency, tag, window duration
                                                              "xxxx" +
                                                              PACKED_UINT32 + PACKED_UINT32)                                                            # window timestamp

PACKED_STREAM_SAMPLE                    = struct.Struct("<" + PACKED_UINT8 +                                                                            # trigger type
                                                              PACKED_UINT8 +                                                                            # stream index
                                                              PACKED_UINT16 +                                                                           # channnel index
                                                              PACKED_UINT32 +                                                                           # sample index
                                                              PACKED_INT32 +                                                                            # I
                                                              PACKED_INT32)                                                                             # Q
