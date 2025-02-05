import pygame
import time
import numpy as np

class render_status:
  def __init__(self, surface, sw_config, hw_interface, sequencer, version):
    self.surface      = surface
    self.hw_interface = hw_interface
    self.sequencer    = sequencer
    self.version      = version

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

    state_str = "{:>20} {:>16}   [{} {}/{}]   {:>4.1f}/{:>4.1f} fps".format(self.sequencer.state, self.sequencer.dwell_state,
      self.sequencer.ecm_controller.state, self.sequencer.ecm_controller.scan_forced_trigger_index, len(self.sequencer.ecm_controller.dwell_channels),
      1.0/mean_time_diff, 1.0/max_time_diff)
    text_data = self.font.render(state_str, True, (0, 192, 192))
    text_rect = text_data.get_rect()
    text_rect.left = 16
    text_rect.bottom = 792
    self.surface.blit(text_data, text_rect)

    text_data = self.font.render(self.version, True, (0, 192, 192))
    text_rect = text_data.get_rect()
    text_rect.left = 1140
    text_rect.bottom = 792
    self.surface.blit(text_data, text_rect)

  def _render_status_window(self):
    status_rect = [1024, 0, 256, 768]
    pygame.draw.rect(self.surface, self.colors["border"], status_rect, 1)

    #TODO: hardware error count

    hw_stats = self.sequencer.hw_stats.stats

    stats_desc = [
                  {"format": "Dwell/sec         : {:.1f}", "value": hw_stats["dwells_per_sec"],                           "pos_offset": [8, 16] },
                  {"format": "Scan time         : {:.6f}", "value": hw_stats["scan_time"],                                "pos_offset": [8, 32] },
                  {"format": "Dwell rpt total   : {}",     "value": hw_stats["dwell_report_total"],                       "pos_offset": [8, 48] },
                  {"format": "DRFM sum rpt tot  : {}",     "value": hw_stats["drfm_summary_report_total"],                "pos_offset": [8, 64] },
                  {"format": "DRFM chan rpt tot : {}",     "value": hw_stats["drfm_channel_report_total"],                "pos_offset": [8, 80] },
                  {"format": "DRFM dwells w/wr  : {}",     "value": hw_stats["drfm_dwells_with_writes"],                  "pos_offset": [8, 96] },
                  {"format": "DRFM dwells w/rd  : {}",     "value": hw_stats["drfm_dwells_with_reads"],                   "pos_offset": [8, 112]},
                  {"format": "Dwell cv meas req : {:.3f}", "value": hw_stats["dwell_coverage_meas_req"],                  "pos_offset": [8, 128]},
                  {"format": "Dwell cv meas act : {:.3f}", "value": hw_stats["dwell_coverage_meas_active"],               "pos_offset": [8, 144]},
                  {"format": "Dwell cv tot meas : {:.3f}", "value": hw_stats["dwell_coverage_total_meas"],                "pos_offset": [8, 160]},
                  {"format": "Dwell cv tot all  : {:.3f}", "value": hw_stats["dwell_coverage_total_all"],                 "pos_offset": [8, 176]},
                  {"format": "Dwell gap frac    : {:.3f}", "value": hw_stats["dwell_gap_fraction"],                       "pos_offset": [8, 192]},
                  {"format": "Dwell total time  : {:.1f}", "value": hw_stats["dwell_time_total_sec"],                     "pos_offset": [8, 208]},
                  {"format": "Rpt dly chan wr   : {}",     "value": hw_stats["drfm_total_channel_write_report_delay"], "pos_offset": [8, 224]},
                  {"format": "Rpt dly sumry wr  : {}",     "value": hw_stats["drfm_total_summary_write_report_delay"], "pos_offset": [8, 240]},
                  {"format": "Rpt dly sumry st  : {}",     "value": hw_stats["drfm_total_summary_start_report_delay"], "pos_offset": [8, 256]},
                  #{"format": "PDW dwells missing: {}",     "value": hw_stats["pdw_dwells_missing"],                       "pos_offset": [8, 272]},
                  {"format": "HW commands sent  : {}",     "value": self.hw_interface.hwcp.num_commands,        "pos_offset": [8, 288]},
                  {"format": "HW DMA writes     : {}",     "value": self.hw_interface.hwcp.num_dma_writes,      "pos_offset": [8, 304]},
                  {"format": "HW DMA reads      : {}",     "value": self.hw_interface.hwdr.num_dma_reads,       "pos_offset": [8, 320]},
                  {"format": "HW status reports : {}",     "value": self.hw_interface.hwdr.num_status_reports,  "pos_offset": [8, 336]},
                  {"format": "HW temp AD9361    : {:.1f}", "value": self.hw_interface.temp_9361,                "pos_offset": [8, 352]},
                  {"format": "HW temp FPGA      : {:.1f}", "value": self.hw_interface.temp_fpga,                "pos_offset": [8, 368]},
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
