import struct

PACKED_UINT8  = "B"
PACKED_UINT16 = "H"
PACKED_INT16  = "h"
PACKED_UINT32 = "I"
PACKED_UINT64 = "Q"

UDP_FILTER_PORT                                 = 65200

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
ECM_ACTIVE_CHANNEL_DRFM_SEGMENT_MAP             = [0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 0]

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

DDS_CONTROL_TYPE_NONE                           = 0
DDS_CONTROL_TYPE_LFSR                           = 1
DDS_CONTROL_TYPE_SIN_SWEEP                      = 2
DDS_CONTROL_TYPE_SIN_STEP                       = 3

ECM_NUM_FAST_LOCK_PROFILES                      = 8
ECM_NUM_DWELL_ENTRIES                           = 32
ECM_NUM_CHANNEL_CONTROL_ENTRIES                 = ECM_NUM_CHANNELS * ECM_NUM_DWELL_ENTRIES

ECM_CHANNEL_TRIGGER_MODE_NONE                   = 0
ECM_CHANNEL_TRIGGER_MODE_FORCE_TRIGGER          = 1
ECM_CHANNEL_TRIGGER_MODE_THRESHOLD_TRIGGER      = 2
ECM_NUM_CHANNEL_TX_PROGRAM_ENTRIES              = 4

ECM_DRFM_MEM_DEPTH                              = 1024 * 32
ECM_DRFM_MAX_PACKET_IQ_SAMPLES_PER_REPORT       = 116
ECM_DRFM_SEGMENT_HYST_SHIFT_WIDTH               = 4 #TODO: better name

ADC_CLOCK_FREQUENCY                             = 61.44e6
ADC_CLOCK_PERIOD                                = 1/61.44e6
FAST_CLOCK_PERIOD                               = 1/(4*61.44e6)
CHANNELIZER_OVERSAMPLING                        = 2.0

ECM_WORDS_PER_DMA_PACKET                        = 128
DMA_TRANSFER_SIZE                               = ECM_WORDS_PER_DMA_PACKET * 4

ETH_MAC_HEADER_LENGTH                           = 14
ETH_IPV4_HEADER_LENGTH                          = 20
ETH_UDP_HEADER_LENGTH                           = 8

PACKED_ECM_REPORT_COMMON_HEADER   = struct.Struct("<" + PACKED_UINT32 + PACKED_UINT32 + "xx" + PACKED_UINT8 + PACKED_UINT8)
PACKED_ECM_CONFIG_HEADER          = struct.Struct("<" + PACKED_UINT32 + PACKED_UINT32 + PACKED_UINT16 + PACKED_UINT8 + PACKED_UINT8 + "xxxx")
PACKED_ECM_CONFIG_CONTROL         = struct.Struct("<" + PACKED_UINT32 + PACKED_UINT32 + PACKED_UINT16 + PACKED_UINT8 + PACKED_UINT8 + "xxxx" +
                                                        PACKED_UINT8 + PACKED_UINT8 + PACKED_UINT8 + PACKED_UINT8 + "xxxx")


PACKED_STATUS_REPORT = struct.Struct("<" + PACKED_UINT32 + PACKED_UINT32 + "xx" + PACKED_UINT8 + PACKED_UINT8 +
                                           PACKED_UINT32 + PACKED_UINT32 + PACKED_UINT32 + PACKED_UINT32 + PACKED_UINT32)

PACKED_ECM_DWELL_PROGRAM_ENTRY = struct.Struct("<" + PACKED_UINT8 + PACKED_UINT8 + PACKED_UINT16 +          #enable, initial_dwell_index, global_counter_init,
                                                     PACKED_UINT16 + PACKED_UINT16 +                        #reporting_threshold_drfm, reporting_threshold_stats
                                                     PACKED_UINT16 + "xxxxxx")                              #tag, padding

PACKED_ECM_DWELL_ENTRY  = struct.Struct("<" + PACKED_UINT8 + PACKED_UINT8 + PACKED_UINT8 + PACKED_UINT8 +   #flags, repeat_count, fast_lock_profile, next_dwell_index
                                              PACKED_UINT16 + PACKED_UINT16 +                               #pre lock, post lock delay
                                              PACKED_UINT16 + PACKED_UINT16 +                               #tag, frequency
                                              PACKED_UINT32 +                                               #measurement_duration
                                              PACKED_UINT32 +                                               #total_duration_max
                                              PACKED_UINT16 + "xx")                                         #min_trigger_duration, padding

PACKED_ECM_CHANNEL_CONTROL_ENTRY_HEADER = struct.Struct("<" + PACKED_UINT8 + PACKED_UINT8 + PACKED_UINT16 + #enable, trigger_mode, trigger_duration_max_minus_one
                                                              PACKED_UINT32 +                               #trigger_threshold
                                                              PACKED_UINT8 + PACKED_UINT8 + PACKED_UINT16   #trigger_hyst_shift, drfm_gain, recording_address
                                                              )

PACKED_ECM_CHANNEL_TX_PROGRAM_ENTRY     = struct.Struct("<" + PACKED_UINT8 + PACKED_UINT8 + PACKED_UINT16 + #valid, trigger_immediate_after_min, tx_instruction_index
                                                              PACKED_UINT16 + PACKED_UINT16)                #duration_gate_min_minus_one, duration_gate_max_minus_one
PACKED_ECM_CHANNEL_CONTROL_ENTRY_PADDING = struct.Struct("<" + "xxxx")

PACKED_ECM_TX_INSTRUCTION                     = struct.Struct("<" + PACKED_UINT64)
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
                                                PACKED_UINT16 + "xx" +                                                  #dwell_entry: min_trigger_duration
                                                PACKED_UINT32 +                                                         #dwell_seq_num
                                                PACKED_UINT16 + PACKED_UINT16 +                                         #program tag, global counter
                                                PACKED_UINT32 +                                                         #actual_measurement_duration
                                                PACKED_UINT32 +                                                         #tx active flag (31), actual_total_duration (30:0)
                                                PACKED_UINT32 + PACKED_UINT32 +                                         #ts_dwell_start
                                                PACKED_UINT32 + PACKED_UINT32 +                                         #total cycles since last report
                                                PACKED_UINT32 + PACKED_UINT32 +                                         #active measurement cycles since last report
                                                PACKED_UINT32 + PACKED_UINT32)                                          #active tx cycles since last report

PACKED_DWELL_STATS_CHANNEL_ENTRY = struct.Struct("<" + PACKED_UINT32 + PACKED_UINT32 + PACKED_UINT32 + PACKED_UINT32)

PACKED_DRFM_SUMMARY_REPORT_HEADER = struct.Struct("<" + PACKED_UINT32 + PACKED_UINT32 + "xx" + PACKED_UINT8 + PACKED_UINT8 +    #common report header
                                                        PACKED_UINT32 +                                                         #dwell_seq_num
                                                        PACKED_UINT16 + PACKED_UINT16 +                                         #channel_was_written, channel_was_read
                                                        PACKED_UINT32 +                                                         #report_delay_channel_write
                                                        PACKED_UINT32 +                                                         #report_delay_summary_write
                                                        PACKED_UINT32)                                                          #report_delay_summary_start

PACKED_DRFM_CHANNEL_REPORT_HEADER = struct.Struct("<" + PACKED_UINT32 + PACKED_UINT32 + "xx" + PACKED_UINT8 + PACKED_UINT8 +    #common report header
                                                        PACKED_UINT32 +                                                         #dwell_seq_num
                                                        "x" + PACKED_UINT8 + PACKED_UINT8 + PACKED_UINT8 +                      #padding, trigger_forced, channel_index, max_iq_bits
                                                        PACKED_UINT32 +                                                         #segment_seq_num
                                                        PACKED_UINT32 + PACKED_UINT32 +                                         #segment_timestamp
                                                        PACKED_UINT16 + PACKED_UINT16 +                                         #segment_addr_first, segment_addr_last
                                                        PACKED_UINT16 + PACKED_UINT16)                                          #slice_addr, slice_length
PACKED_DRFM_IQ_WORD = struct.Struct("<" + PACKED_INT16 + PACKED_INT16)

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