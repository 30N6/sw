import struct

PACKED_UINT8  = "B"
PACKED_UINT16 = "H"
PACKED_INT16  = "h"
PACKED_UINT32 = "I"
PACKED_UINT64 = "Q"

ECM_CONTROL_MAGIC_NUM                           = 0x45434D43
ECM_REPORT_MAGIC_NUM                            = 0x45434D52

ECM_MODULE_ID_CONTROL                           = 0x00
ECM_MODULE_ID_DWELL_CONTROLLER                  = 0x01
ECM_MODULE_ID_DWELL_STATS                       = 0x02
ECM_MODULE_ID_DRFM                              = 0x05
ECM_MODULE_ID_STATUS                            = 0x06

ECM_CONTROL_MESSAGE_TYPE_ENABLE                 = 0x00
ECM_CONTROL_MESSAGE_TYPE_DWELL_PROGRAM          = 0x01
ECM_CONTROL_MESSAGE_TYPE_DWELL_ENTRY            = 0x02
ECM_CONTROL_MESSAGE_TYPE_DWELL_CHANNEL_CONTROL  = 0x03
ECM_CONTROL_MESSAGE_TYPE_DWELL_TX_INSTRUCTION   = 0x04
ECM_REPORT_MESSAGE_TYPE_DWELL_STATS             = 0x10
ECM_REPORT_MESSAGE_TYPE_DRFM_CHANNEL_DATA       = 0x20
ECM_REPORT_MESSAGE_TYPE_DRFM_SUMMARY            = 0x21
ECM_REPORT_MESSAGE_TYPE_STATUS                  = 0x30

ECM_NUM_CHANNELS                                = 16
ECM_NUM_CHANNELS_ACTIVE                         = 13  # remove split channel + two edge channels
ECM_CHANNEL_MASK                                = 0x7FFC

ECM_NUM_TX_INSTRUCTIONS                         = 512

ECM_TX_INSTRUCTION_TYPE_NOP                     = 0
ECM_TX_INSTRUCTION_TYPE_DDS_SETUP_BPSK          = 1
ECM_TX_INSTRUCTION_TYPE_DDS_SETUP_CW_SWEEP      = 2
ECM_TX_INSTRUCTION_TYPE_DDS_SETUP_CW_STEP       = 3
ECM_TX_INSTRUCTION_TYPE_PLAYBACK                = 4
ECM_TX_INSTRUCTION_TYPE_WAIT                    = 5
ECM_TX_INSTRUCTION_TYPE_JUMP                    = 6

ECM_TX_OUTPUT_CONTROL_DISABLED                  = 0
ECM_TX_OUTPUT_CONTROL_DDS                       = 1
ECM_TX_OUTPUT_CONTROL_DRFM                      = 2
ECM_TX_OUTPUT_CONTROL_MIXER                     = 3
ECM_TX_OUTPUT_CONTROL_WIDTH                     = 2

ECM_NUM_FAST_LOCK_PROFILES                      = 8
ECM_NUM_DWELL_ENTRIES                           = 32
ECM_NUM_CHANNEL_CONTROL_ENTRIES                 = ECM_NUM_CHANNELS * ECM_NUM_DWELL_ENTRIES

ECM_CHANNEL_TRIGGER_MODE_NONE                   = 0
ECM_CHANNEL_TRIGGER_MODE_FORCE_TRIGGER          = 1
ECM_CHANNEL_TRIGGER_MODE_THRESHOLD_TRIGGER      = 2
ECM_NUM_CHANNEL_TX_PROGRAM_ENTRIES              = 4

ECM_DRFM_MEM_DEPTH                              = 1024 * 24
ECM_DRFM_MAX_PACKET_IQ_SAMPLES_PER_REPORT       = 116

ADC_CLOCK_FREQUENCY                             = 61.44e6
ADC_CLOCK_PERIOD                                = 1/61.44e6
FAST_CLOCK_PERIOD                               = 1/(4*61.44e6)
CHANNELIZER_OVERSAMPLING                        = 2.0

ECM_WORDS_PER_DMA_PACKET                        = 128
DMA_TRANSFER_SIZE                               = ECM_WORDS_PER_DMA_PACKET * 4

PACKED_ECM_REPORT_COMMON_HEADER   = struct.Struct("<" + PACKED_UINT32 + PACKED_UINT32 + "xx" + PACKED_UINT8 + PACKED_UINT8)
PACKED_ECM_CONFIG_HEADER          = struct.Struct("<" + PACKED_UINT32 + PACKED_UINT32 + PACKED_UINT16 + PACKED_UINT8 + PACKED_UINT8 + "xxxx")
PACKED_ECM_CONFIG_CONTROL         = struct.Struct("<" + PACKED_UINT32 + PACKED_UINT32 + PACKED_UINT16 + PACKED_UINT8 + PACKED_UINT8 + "xxxx" +
                                                        PACKED_UINT8 + PACKED_UINT8 + PACKED_UINT8 + PACKED_UINT8 + "xxxx")


PACKED_STATUS_REPORT = struct.Struct("<" + PACKED_UINT32 + PACKED_UINT32 + "xx" + PACKED_UINT8 + PACKED_UINT8 +
                                           PACKED_UINT32 + PACKED_UINT32 + PACKED_UINT32 + PACKED_UINT32 + PACKED_UINT32)

PACKED_ECM_DWELL_PROGRAM_ENTRY = struct.Struct("<" + PACKED_UINT8 + PACKED_UINT8 + PACKED_UINT16 + "xxxx")  #enable, initial_dwell_index, global_counter_init, padding

PACKED_ECM_DWELL_ENTRY  = struct.Struct("<" + PACKED_UINT8 + PACKED_UINT8 + PACKED_UINT8 + PACKED_UINT8 +   #flags, repeat_count, fast_lock_profile, next_dwell_index
                                              PACKED_UINT16 + PACKED_UINT16 +                               #pre lock, post lock delay
                                              PACKED_UINT16 + PACKED_UINT16 +                               #tag, frequency
                                              PACKED_UINT32 +                                               #measurement_duration
                                              PACKED_UINT32 +                                               #total_duration_max
                                              "xxxx")                                                       #padding

PACKED_ECM_CHANNEL_CONTROL_ENTRY_HEADER = struct.Struct("<" + PACKED_UINT8 + PACKED_UINT8 + PACKED_UINT16 + #enable, trigger_mode, trigger_duration_max_minus_one
                                                              PACKED_UINT32 +                               #trigger_threshold
                                                              PACKED_UINT8 + PACKED_UINT8 + PACKED_UINT16 + #trigger_hyst_shift, drfm_gain, recording_address
                                                              "xxxx")

PACKED_ECM_CHANNEL_TX_PROGRAM_ENTRY     = struct.Struct("<" + PACKED_UINT8 + PACKED_UINT8 + PACKED_UINT16 + #valid, trigger_immediate_after_min, tx_instruction_index
                                                              PACKED_UINT16 + PACKED_UINT16)                #duration_gate_min_minus_one, duration_gate_max_minus_one

PACKED_ECM_TX_INSTRUCTION_HEADER              = struct.Struct("<" + PACKED_UINT16)
PACKED_ECM_TX_INSTRUCTION_DDS_SETUP_BPSK      = struct.Struct("<" + PACKED_UINT16 + PACKED_UINT16 + "xxxx")
PACKED_ECM_TX_INSTRUCTION_DDS_SETUP_CW_SWEEP  = struct.Struct("<" + PACKED_UINT16 + PACKED_UINT16 + PACKED_UINT16 + PACKED_UINT16)
PACKED_ECM_TX_INSTRUCTION_DDS_SETUP_CW_STEP   = struct.Struct("<" + PACKED_UINT16 + PACKED_UINT16 + PACKED_UINT16 + PACKED_UINT16)
PACKED_ECM_TX_INSTRUCTION_PLAYBACK            = struct.Struct("<" + PACKED_UINT16 + PACKED_UINT16 + PACKED_UINT16 + PACKED_UINT16)
PACKED_ECM_TX_INSTRUCTION_WAIT                = struct.Struct("<" + PACKED_UINT16 + PACKED_UINT8 + PACKED_UINT8 + PACKED_UINT8 + PACKED_UINT8 + PACKED_UINT8 + PACKED_UINT8)
PACKED_ECM_TX_INSTRUCTION_JUMP                = struct.Struct("<" + PACKED_UINT16 + PACKED_UINT16 + PACKED_UINT8 + PACKED_UINT16 + "x")


PACKED_DWELL_STATS_HEADER = struct.Struct("<" + PACKED_UINT32 + PACKED_UINT32 + "xx" + PACKED_UINT8 + PACKED_UINT8 +    #common report header
                                                PACKED_UINT8 + PACKED_UINT8 + PACKED_UINT8 + PACKED_UINT8 +             #dwell_entry: packed flags, repeat_count, fast_lock_profile, next_dwell_index
                                                PACKED_UINT16 + PACKED_UINT16 +                                         #dwell_entry: pll_pre_lock_delay, pll_post_lock_delay
                                                PACKED_UINT16 + PACKED_UINT16 +                                         #dwell_entry: tag, frequency
                                                PACKED_UINT32 +                                                         #dwell_entry: measurement_duration
                                                PACKED_UINT32 +                                                         #dwell_entry: total_duration_max
                                                PACKED_UINT32 +                                                         #dwell_seq_num
                                                PACKED_UINT32 +                                                         #global counter
                                                PACKED_UINT32 +                                                         #actual_measurement_duration
                                                PACKED_UINT32 +                                                         #actual_total_duration
                                                PACKED_UINT32 + PACKED_UINT32)                                          #ts_dwell_start

PACKED_DWELL_STATS_CHANNEL_ENTRY = struct.Struct("<" + PACKED_UINT32 + PACKED_UINT32 + PACKED_UINT32 + PACKED_UINT32)

#TODO
#
#PACKED_PDW_PULSE_REPORT_HEADER = struct.Struct("<" + PACKED_UINT32 + PACKED_UINT32 + "xx" + PACKED_UINT8 + PACKED_UINT8 +
#                                                     PACKED_UINT32 +
#                                                     PACKED_UINT32 +
#                                                     PACKED_UINT32 +
#                                                     PACKED_UINT32 +
#                                                     PACKED_UINT32 + PACKED_UINT32 +
#                                                     PACKED_UINT32 +
#                                                     PACKED_UINT32 +
#                                                     PACKED_UINT32 + PACKED_UINT32 +
#                                                     "xx" + PACKED_UINT8 + PACKED_UINT8)
#
#PACKED_PDW_PULSE_IQ_WORD = struct.Struct("<" + PACKED_INT16 + PACKED_INT16)
#NUM_PDW_PULSE_TRAILER_WORDS = (DMA_TRANSFER_SIZE - PACKED_PDW_PULSE_REPORT_HEADER.size) // PACKED_PDW_PULSE_IQ_WORD.size
#
#
#PACKED_PDW_SUMMARY_REPORT_HEADER = struct.Struct("<" + PACKED_UINT32 + PACKED_UINT32 + "xx" + PACKED_UINT8 + PACKED_UINT8 +
#                                                       PACKED_UINT32 +
#                                                       PACKED_UINT32 + PACKED_UINT32 +
#                                                       PACKED_UINT32 +
#                                                       PACKED_UINT32 +
#                                                       PACKED_UINT32 +
#                                                       PACKED_UINT32 +
#                                                       PACKED_UINT32)
#