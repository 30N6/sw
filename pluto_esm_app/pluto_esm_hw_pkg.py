import struct

PACKED_UINT8  = "B"
PACKED_UINT16 = "H"
PACKED_INT16  = "h"
PACKED_UINT32 = "I"
PACKED_UINT64 = "Q"

ESM_REPORT_MAGIC_NUM                    = 0x45534D52
ESM_CONTROL_MAGIC_NUM                   = 0x45534D43

ESM_MODULE_ID_CONTROL                   = 0x00
ESM_MODULE_ID_DWELL_CONTROLLER          = 0x01
ESM_MODULE_ID_DWELL_STATS_NARROW        = 0x02
ESM_MODULE_ID_DWELL_STATS_WIDE          = 0x03
ESM_MODULE_ID_PDW_NARROW                = 0x04
ESM_MODULE_ID_PDW_WIDE                  = 0x05

ESM_CONTROL_MESSAGE_TYPE_ENABLE         = 0x00
ESM_CONTROL_MESSAGE_TYPE_DWELL_ENTRY    = 0x01
ESM_CONTROL_MESSAGE_TYPE_DWELL_PROGRAM  = 0x02

ESM_REPORT_MESSAGE_TYPE_DWELL_STATS     = 0x11
ESM_REPORT_MESSAGE_TYPE_PDW_PULSE       = 0x20
ESM_REPORT_MESSAGE_TYPE_PDW_SUMMARY     = 0x21
ESM_REPORT_MESSAGE_TYPE_STATUS          = 0x30

ESM_NUM_CHANNELS_WIDE                   = 8
ESM_NUM_CHANNELS_NARROW                 = 64

ESM_NUM_DWELL_ENTRIES                   = 256
ESM_NUM_DWELL_INSTRUCTIONS              = 32
ESM_NUM_FAST_LOCK_PROFILES              = 8
ADC_CLOCK_FREQUENCY                     = 61.44e6
ADC_CLOCK_PERIOD                        = 1/61.44e6
FAST_CLOCK_PERIOD                       = 1/(4*61.44e6)
CHANNELIZER_OVERSAMPLING                = 2.0

ESM_PDW_BUFFERED_SAMPLES_PER_FRAME      = 48
ESM_PDW_BUFFERED_IQ_DELAY_SAMPLES       = 8

TRANSFER_SIZE = 256

PACKED_ESM_REPORT_COMMON_HEADER   = struct.Struct("<" + PACKED_UINT32 + PACKED_UINT32 + "xx" + PACKED_UINT8 + PACKED_UINT8)
PACKED_ESM_CONFIG_HEADER          = struct.Struct("<" + PACKED_UINT32 + PACKED_UINT32 + "xx" + PACKED_UINT8 + PACKED_UINT8 + "xxxx")
PACKED_ESM_CONFIG_CONTROL         = struct.Struct("<" + PACKED_UINT32 + PACKED_UINT32 + "xx" + PACKED_UINT8 + PACKED_UINT8 + "xxxx" +
                                                        PACKED_UINT8 + PACKED_UINT8 + PACKED_UINT8 + PACKED_UINT8 + "xxxx")

PACKED_ESM_MESSAGE_DWELL_ENTRY    = struct.Struct("<" + PACKED_UINT8 + "xxx" + "xxxx" +
                                                        PACKED_UINT16 + PACKED_UINT16 +
                                                        PACKED_UINT32 +
                                                        PACKED_UINT8 + PACKED_UINT8 + "xx" +
                                                        PACKED_UINT8 + PACKED_UINT8 + "xx" +
                                                        PACKED_UINT64 +
                                                        PACKED_UINT8 + "x" + PACKED_UINT16 +
                                                        "xxxx")

PACKED_DWELL_INSTRUCTION          = struct.Struct("<" + PACKED_UINT8 + PACKED_UINT8 + PACKED_UINT8 + PACKED_UINT8)
PACKED_DWELL_PROGRAM              = struct.Struct("<" + PACKED_UINT8 + PACKED_UINT8 + "xx" + PACKED_UINT32 + PACKED_UINT64)

PACKED_DWELL_STATS_HEADER = struct.Struct("<" + PACKED_UINT32 + PACKED_UINT32 + "xx" + PACKED_UINT8 + PACKED_UINT8 +
                                                PACKED_UINT32 +
                                                PACKED_UINT16 + PACKED_UINT16 +
                                                PACKED_UINT32 +
                                                PACKED_UINT8 + PACKED_UINT8 + PACKED_UINT8 + PACKED_UINT8 +
                                                "xx" + PACKED_UINT8 + PACKED_UINT8 +
                                                "xxxx" +
                                                "xxxxxxxx" + "xxxx" +
                                                PACKED_UINT32 +
                                                PACKED_UINT32 +
                                                PACKED_UINT32 + PACKED_UINT32 +
                                                PACKED_UINT32 + PACKED_UINT32)
PACKED_DWELL_STATS_CHANNEL_ENTRY = struct.Struct("<" + PACKED_UINT32 + PACKED_UINT32 + PACKED_UINT32 + PACKED_UINT32)
NUM_DWELL_STATS_TRAILER_BYTES = TRANSFER_SIZE - PACKED_DWELL_STATS_HEADER.size

PACKED_STATUS_REPORT = struct.Struct("<" + PACKED_UINT32 + PACKED_UINT32 + "xx" + PACKED_UINT8 + PACKED_UINT8 +
                                           PACKED_UINT32 + PACKED_UINT32 + PACKED_UINT32 + PACKED_UINT32 + PACKED_UINT32 + PACKED_UINT32)


PACKED_PDW_PULSE_REPORT_HEADER = struct.Struct("<" + PACKED_UINT32 + PACKED_UINT32 + "xx" + PACKED_UINT8 + PACKED_UINT8 +
                                                     PACKED_UINT32 +
                                                     PACKED_UINT32 +
                                                     PACKED_UINT32 +
                                                     PACKED_UINT32 +
                                                     PACKED_UINT32 + PACKED_UINT32 +
                                                     PACKED_UINT32 +
                                                     PACKED_UINT32 +
                                                     PACKED_UINT32 + PACKED_UINT32 +
                                                     "xx" + PACKED_UINT8 + PACKED_UINT8)

PACKED_PDW_PULSE_IQ_WORD = struct.Struct("<" + PACKED_INT16 + PACKED_INT16)
NUM_PDW_PULSE_TRAILER_WORDS = (TRANSFER_SIZE - PACKED_PDW_PULSE_REPORT_HEADER.size) // PACKED_PDW_PULSE_IQ_WORD.size


PACKED_PDW_SUMMARY_REPORT_HEADER = struct.Struct("<" + PACKED_UINT32 + PACKED_UINT32 + "xx" + PACKED_UINT8 + PACKED_UINT8 +
                                                       PACKED_UINT32 +
                                                       PACKED_UINT32 + PACKED_UINT32 +
                                                       PACKED_UINT32 +
                                                       PACKED_UINT32 +
                                                       PACKED_UINT32 +
                                                       PACKED_UINT32 +
                                                       PACKED_UINT32)
