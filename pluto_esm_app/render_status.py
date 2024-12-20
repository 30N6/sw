import pygame
import time
import numpy as np

class render_status:
  def __init__(self, surface, sw_config, sequencer, version):
    self.surface    = surface
    self.sequencer  = sequencer
    self.version    = version

    self.colors = {}
    self.colors["border"] = (0, 0, 255)
    self.colors["stats"]  = (0, 192, 192)

    self.font = pygame.font.SysFont('Consolas', 14)

    self.frame_times = np.zeros(50)

  def _render_status_bar(self):
    self.frame_times = np.roll(self.frame_times, 1)
    self.frame_times[0] = time.time()
    time_diff = -np.diff(self.frame_times)
    mean_time_diff = np.mean(time_diff)
    max_time_diff = np.max(time_diff)

    state_str = "{:>20} {:>16} {:>4.1f}/{:>4.1f} fps".format(self.sequencer.state, self.sequencer.dwell_state, 1.0/mean_time_diff, 1.0/max_time_diff)
    text_data = self.font.render(state_str, True, (0, 192, 192))
    text_rect = text_data.get_rect()
    text_rect.left = 16
    text_rect.bottom = 792
    self.surface.blit(text_data, text_rect)

    text_data = self.font.render(self.version, True, (0, 192, 192))
    text_rect = text_data.get_rect()
    text_rect.left = 1150
    text_rect.bottom = 792
    self.surface.blit(text_data, text_rect)

  def _render_status_window(self):
    status_rect = [1024, 0, 256, 768]
    pygame.draw.rect(self.surface, self.colors["border"], status_rect, 1)

    hw_stats = self.sequencer.hw_stats.stats

    stats_desc = [{"format": "Dwell/sec         : {:.1f}", "value": hw_stats["dwells_per_sec"],                           "pos_offset": [8, 16] },
                  {"format": "Scan time         : {:.1f}", "value": hw_stats["scan_time"],                                "pos_offset": [8, 32] },
                  {"format": "PPS total         : {}",     "value": hw_stats["pps_total"],                                "pos_offset": [8, 48] },
                  {"format": "PPS drops         : {}",     "value": hw_stats["pps_dropped"],                              "pos_offset": [8, 64] },
                  {"format": "Scan pulse total  : {}",     "value": hw_stats["scan_pulses_total"],                        "pos_offset": [8, 80] },
                  {"format": "Scan pulse drops  : {}",     "value": hw_stats["scan_pulses_dropped"],                      "pos_offset": [8, 96] },
                  {"format": "Tot pulses        : {}",     "value": hw_stats["pulses_total"],                             "pos_offset": [8, 112]},
                  {"format": "Tot pulses dropped: {}",     "value": hw_stats["pulses_dropped"],                           "pos_offset": [8, 128]},
                  {"format": "Tot pulses accpted: {}",     "value": hw_stats["pulses_accepted"],                          "pos_offset": [8, 144]},
                  {"format": "Scan ack dly rpt  : {:.3f}", "value": hw_stats["scan_ack_delay_report"],                    "pos_offset": [8, 160]},
                  {"format": "Scan ack dly sp   : {:.3f}", "value": hw_stats["scan_ack_delay_sample_proc"],               "pos_offset": [8, 176]},
                  {"format": "Dwell covrg fine  : {:.6f}", "value": hw_stats["dwell_coverage_fine"],                      "pos_offset": [8, 192]},
                  {"format": "PDW covrg fine    : {:.6f}", "value": hw_stats["pdw_coverage_fine"],                        "pos_offset": [8, 208]},
                  {"format": "Dwell covrg coarse: {:.2f}", "value": hw_stats["dwell_coverage_coarse"],                    "pos_offset": [8, 224]},
                  {"format": "PDW covrg coarse  : {:.2f}", "value": hw_stats["pdw_coverage_coarse"],                      "pos_offset": [8, 240]},
                  {"format": "PDW IQ rcrd covrg : {:.2f}", "value": hw_stats["pdw_recording_coverage"],                   "pos_offset": [8, 256]},
                  {"format": "PDW dwells missing: {}",     "value": hw_stats["pdw_dwells_missing"],                       "pos_offset": [8, 272]},
                  {"format": "HW commands sent  : {}",     "value": self.sequencer.hw_interface.hwcp.num_commands,        "pos_offset": [8, 288]},
                  {"format": "HW DMA writes     : {}",     "value": self.sequencer.hw_interface.hwcp.num_dma_writes,      "pos_offset": [8, 304]},
                  {"format": "HW DMA reads      : {}",     "value": self.sequencer.hw_interface.hwdr.num_dma_reads,       "pos_offset": [8, 320]},
                  {"format": "HW status reports : {}",     "value": self.sequencer.hw_interface.hwdr.num_status_reports,  "pos_offset": [8, 336]},
                  ]

    for entry in stats_desc:
      stats_str = entry["format"].format(entry["value"])
      text_data = self.font.render(stats_str, True, self.colors["stats"])
      text_rect = text_data.get_rect()
      text_rect.left = status_rect[0] + entry["pos_offset"][0]
      text_rect.bottom = status_rect[1] + entry["pos_offset"][1]
      self.surface.blit(text_data, text_rect)

  def render(self):
    self._render_status_bar()
    self._render_status_window()

  def update(self):
    pass
