from pluto_ecm_hw_pkg import *
import numpy as np

class pluto_ecm_dwell_stats_buffer:

  def __init__(self, sw_config):
    self.dwell_freqs = []
    for entry in sw_config.config["dwell_config"]["dwell_freqs"]:
      self.dwell_freqs.append(entry["freq"])
    self.num_freqs = len(self.dwell_freqs)

    self.buffer_depth               = 64 #config?
    self.dwell_data_row_index       = 0
    self.dwell_data_last_row_index  = 0
    self.dwell_data_by_freq         = {}

    for freq in self.dwell_freqs:
      self.dwell_data_by_freq[freq] = {}
      self.dwell_data_by_freq[freq]["channel_accum"]     = np.zeros((self.buffer_depth, ECM_NUM_CHANNELS), dtype=np.uint64)
      self.dwell_data_by_freq[freq]["channel_peak"]      = np.zeros((self.buffer_depth, ECM_NUM_CHANNELS), dtype=np.uint32)
      self.dwell_data_by_freq[freq]["channel_duration"]  = np.zeros((self.buffer_depth, ECM_NUM_CHANNELS), dtype=np.uint32)
      self.dwell_data_by_freq[freq]["start_time"]        = np.zeros(self.buffer_depth, dtype=np.uint64)
      self.dwell_data_by_freq[freq]["program_tag"]       = np.zeros(self.buffer_depth, dtype=np.uint32)

  def process_dwell_update(self, dwell_entry):
    dwell_data    = dwell_entry["dwell_data"]
    dwell_report  = dwell_entry["dwell_report"]
    is_first      = dwell_entry["first_in_sequence"]
    is_last       = dwell_entry["last_in_sequence"]

    if is_first:
      for freq in self.dwell_freqs:
        freq_data = self.dwell_data_by_freq[freq]
        freq_data["channel_accum"][self.dwell_data_row_index, :]     = 0
        freq_data["channel_peak"][self.dwell_data_row_index, :]      = 0
        freq_data["channel_duration"][self.dwell_data_row_index, :]  = 0
        freq_data["start_time"][self.dwell_data_row_index]           = dwell_report["ts_dwell_start"]
        freq_data["program_tag"][self.dwell_data_row_index]          = dwell_report["dwell_program_tag"]

    for i in range(ECM_NUM_CHANNELS):
      entry = dwell_report["channel_data"][i]
      freq_data = self.dwell_data_by_freq[dwell_data.frequency]

      freq_data["channel_accum"][self.dwell_data_row_index, i]     += entry["accum"]
      freq_data["channel_peak"][self.dwell_data_row_index, i]      = max(freq_data["channel_peak"][self.dwell_data_row_index, i], entry["max"])
      freq_data["channel_duration"][self.dwell_data_row_index, i]  += entry["cycles"]

    if is_last:
      self.dwell_data_last_row_index  = self.dwell_data_row_index
      self.dwell_data_row_index       = (self.dwell_data_row_index + 1) % self.buffer_depth

    return is_last

