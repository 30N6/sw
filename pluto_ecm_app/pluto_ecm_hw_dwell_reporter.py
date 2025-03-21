from pluto_ecm_hw_pkg import *
import pluto_ecm_hw_dwell

class pluto_ecm_hw_dwell_reporter:
  def __init__(self, logger):
    self.logger = logger
    self.next_msg_seq_num = 0

    self.logger.log(self.logger.LL_INFO, "[pluto_ecm_hw_dwell_reporter] init")

  def _process_common_header(self, data):
    assert (len(data) == DMA_TRANSFER_SIZE)
    unpacked_header = PACKED_ECM_REPORT_COMMON_HEADER.unpack(data[:PACKED_ECM_REPORT_COMMON_HEADER.size])

    magic_num   = unpacked_header[0]
    msg_seq_num = unpacked_header[1]
    msg_type    = unpacked_header[2]
    mod_id      = unpacked_header[3]

    assert (magic_num == ECM_REPORT_MAGIC_NUM)
    assert (msg_type == ECM_REPORT_MESSAGE_TYPE_DWELL_STATS)
    assert (mod_id == ECM_MODULE_ID_DWELL_STATS)

    if msg_seq_num != self.next_msg_seq_num:
      self.logger.log(self.logger.LL_WARN, "Dwell stats seq num gap: expected {}, received {}".format(self.next_msg_seq_num, msg_seq_num))
    self.next_msg_seq_num = (msg_seq_num + 1) & 0xFFFFFFFF

  def process_message(self, data):
    self._process_common_header(data)

    unpacked_header = PACKED_DWELL_STATS_HEADER.unpack(data[:PACKED_DWELL_STATS_HEADER.size])

    packed_flags = unpacked_header[7]

    report = {}

    report["dwell_entry_valid"]                   = (packed_flags & (1 << 0)) != 0
    report["dwell_entry_global_counter_check"]    = (packed_flags & (1 << 1)) != 0
    report["dwell_entry_global_counter_dec"]      = (packed_flags & (1 << 2)) != 0
    report["dwell_entry_skip_pll_prelock_wait"]   = (packed_flags & (1 << 3)) != 0
    report["dwell_entry_skip_pll_lock_check"]     = (packed_flags & (1 << 4)) != 0
    report["dwell_entry_skip_pll_postlock_wait"]  = (packed_flags & (1 << 5)) != 0
    report["dwell_entry_repeat_count"]            = unpacked_header[6]
    report["dwell_entry_fast_lock_profile"]       = unpacked_header[5]
    report["dwell_entry_next_dwell_index"]        = unpacked_header[4]

    report["dwell_entry_pll_pre_lock_delay"]      = unpacked_header[9]
    report["dwell_entry_pll_post_lock_delay"]     = unpacked_header[8]

    report["dwell_entry_tag"]                     = unpacked_header[11]
    report["dwell_entry_frequency"]               = unpacked_header[10]

    report["dwell_entry_measurement_duration"]    = unpacked_header[12]
    report["dwell_entry_total_duration_max"]      = unpacked_header[13]
    report["dwell_min_trigger_duration"]          = unpacked_header[14]

    report["dwell_seq_num"]                       = unpacked_header[15]

    report["dwell_program_tag"]                   = unpacked_header[17]
    report["global_counter"]                      = unpacked_header[16]

    report["actual_measurement_duration"]         = unpacked_header[18]
    report["actual_total_duration"]               = unpacked_header[19] & 0x7FFFFFFF
    report["dwell_tx_active"]                     = (unpacked_header[19] & 0x80000000) != 0
    report["ts_dwell_start"]                      = (unpacked_header[20] << 32) | unpacked_header[21]
    report["cycles_total"]                        = (unpacked_header[22] << 32) | unpacked_header[23]
    report["cycles_active_meas"]                  = (unpacked_header[24] << 32) | unpacked_header[25]
    report["cycles_active_tx"]                    = (unpacked_header[26] << 32) | unpacked_header[27]

    report["channel_data"] = [{"cycles": 1, "accum": 0, "max": 0} for i in range(ECM_NUM_CHANNELS)]

    #if report["dwell_tx_active"]:
    #  print("dwell_tx_active=1")

    for channel_index_hw in range(ECM_NUM_CHANNELS):
      channel_index = pluto_ecm_hw_dwell.ecm_channel_index_hw_to_sw(channel_index_hw)

      if (ECM_CHANNEL_MASK & (1 << channel_index)) != 0:
        unpacked_channel_entry = PACKED_DWELL_STATS_CHANNEL_ENTRY.unpack(data[(PACKED_DWELL_STATS_HEADER.size + PACKED_DWELL_STATS_CHANNEL_ENTRY.size * channel_index_hw) :
                                                                              (PACKED_DWELL_STATS_HEADER.size + PACKED_DWELL_STATS_CHANNEL_ENTRY.size * (channel_index_hw + 1))])
        channel_cycles  = unpacked_channel_entry[0]
        channel_accum   = (unpacked_channel_entry[1] << 32) | unpacked_channel_entry[2]
        channel_max     = unpacked_channel_entry[3]

        report["channel_data"][channel_index] = {"cycles": channel_cycles, "accum": channel_accum, "max": channel_max}

    return report
