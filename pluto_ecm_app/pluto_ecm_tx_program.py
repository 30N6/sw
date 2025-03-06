import json
import os
from pluto_ecm_hw_pkg import *

class pluto_ecm_tx_program:
  def __init__(self, config_data, config_filename):
    self.config = config_data
    self.config_dir = os.path.split(config_filename)[0]

    self.map_instruction_type = { "nop"                 : ECM_TX_INSTRUCTION_TYPE_NOP,
                                  "dds_setup_bpsk"      : ECM_TX_INSTRUCTION_TYPE_DDS_SETUP_BPSK,
                                  "dds_setup_cw_sweep"  : ECM_TX_INSTRUCTION_TYPE_DDS_SETUP_CW_SWEEP,
                                  "dds_setup_cw_step"   : ECM_TX_INSTRUCTION_TYPE_DDS_SETUP_CW_STEP,
                                  "drfm_playback"       : ECM_TX_INSTRUCTION_TYPE_PLAYBACK,
                                  "wait"                : ECM_TX_INSTRUCTION_TYPE_WAIT,
                                  "jump"                : ECM_TX_INSTRUCTION_TYPE_JUMP}
    self.map_output_control = {   "disabled"            : ECM_TX_OUTPUT_CONTROL_DISABLED,
                                  "dds"                 : ECM_TX_OUTPUT_CONTROL_DDS,
                                  "drfm"                : ECM_TX_OUTPUT_CONTROL_DRFM,
                                  "mixer"               : ECM_TX_OUTPUT_CONTROL_MIXER}
    self.map_dds_sin_phase_inc_sel = {"sweep"           : 0,
                                      "step"            : 1}
    self.map_dds_output_sel = { "none"                  : DDS_CONTROL_TYPE_NONE,
                                "lfsr"                  : DDS_CONTROL_TYPE_LFSR,
                                "sweep"                 : DDS_CONTROL_TYPE_SIN_SWEEP,
                                "step"                  : DDS_CONTROL_TYPE_SIN_STEP}
    self.map_playback_mode = {"segment"                 : 0,
                              "cycle"                   : 1}


    self.tx_programs_by_name = {}
    self._load_tx_programs()

    for name, program in self.tx_programs_by_name.items():
      print("tx_program: {}".format(name))
      for instruction in program["instructions"]:
        print("  [{:02}] : {:016X}".format(program["address"], instruction))

  def _load_tx_programs(self):
    raw_program_data = {}
    total_instruction_count = 0

    tx_programs = [entry["tx_program"] for entry in self.config["tx_config"]["signals"]]
    tx_programs.append(self.config["tx_calibration"]["forced_tx_program"])

    for program_name in tx_programs:
      if len(program_name) == 0:
        continue

      tx_program_filename = os.path.join(self.config_dir, program_name)
      with open(tx_program_filename) as fd:
        raw_data = json.load(fd)
        raw_program_data[program_name] = raw_data["instructions"]
        total_instruction_count += len(raw_program_data[program_name])

    assert (total_instruction_count <= ECM_NUM_TX_INSTRUCTIONS)

    instruction_index = 0
    for program_name in raw_program_data:
      raw_data = raw_program_data[program_name]
      self.tx_programs_by_name[program_name] = {"address": instruction_index, "instructions": self._load_tx_program(raw_data, instruction_index)}
      instruction_index += len(raw_data)

  def _load_tx_program(self, raw_data, base_index):
    assert (not raw_data[-1]["valid"])

    packed_instructions = []

    instruction_count = 0
    for entry in raw_data:
      assert (entry["address"] == instruction_count)
      instruction_index = base_index + instruction_count

      converted_data = {}
      converted_data["valid"]                         = entry["valid"]
      converted_data["type"]                          = self.map_instruction_type[entry["type"]]
      converted_data["header_output_valid"]           = entry["output_control"]["valid"]
      converted_data["header_output_control"]         = self.map_output_control[entry["output_control"]["output_sel"]]
      converted_data["header_dds_valid"]              = entry["dds_control"]["valid"]
      converted_data["header_dds_sin_phase_inc_sel"]  = self.map_dds_sin_phase_inc_sel[entry["dds_control"]["sin_phase_inc_sel"]]
      converted_data["header_dds_output_sel"]         = self.map_dds_output_sel[entry["dds_control"]["output_sel"]]

      if entry["type"] == "nop":
        pass
      elif entry["type"] == "dds_setup_bpsk":
        converted_data["dds_lfsr_phase_inc"]                      = entry["lfsr_phase_inc"]
      elif entry["type"] == "dds_setup_cw_sweep":
        converted_data["dds_sin_sweep_phase_inc_start"]           = entry["sin_sweep_phase_inc_start"]
        converted_data["dds_sin_sweep_phase_inc_stop"]            = entry["sin_sweep_phase_inc_stop"]
        converted_data["dds_sin_sweep_phase_inc_step"]            = entry["sin_sweep_phase_inc_step"]
      elif entry["type"] == "dds_setup_cw_step":
        converted_data["dds_sin_step_phase_inc_min"]              = entry["sin_step_phase_inc_min"]
        converted_data["dds_sin_step_phase_inc_rand_offset_mask"] = entry["sin_step_phase_inc_rand_offset_mask"]
        converted_data["dds_sin_step_period_minus_one"]           = entry["sin_step_period_minus_one"]
      elif entry["type"] == "drfm_playback":
        converted_data["playback_mode"]                           = self.map_playback_mode[entry["mode"]]
        converted_data["playback_base_count"]                     = entry["base_count"]
        converted_data["playback_rand_offset_mask"]               = entry["rand_offset_mask"]
      elif entry["type"] == "wait":
        converted_data["wait_base_duration"]                      = entry["base_duration"]
        converted_data["wait_rand_offset_mask"]                   = entry["rand_offset_mask"]
      elif entry["type"] == "jump":
        converted_data["jump_target_address"]                     = entry["target_address"] + base_index
        converted_data["jump_counter_check"]                      = entry["counter_check"]
        converted_data["jump_counter_value"]                      = entry["counter_value"]
      else:
        raise RuntimeError("invalid instruction type")

      packed_instructions.append(self._pack_tx_instruction(converted_data))

      instruction_count += 1

    return packed_instructions

  def _pack_tx_instruction(self, data):
    r = self._pack_tx_instruction_header(data)

    if data["type"] == ECM_TX_INSTRUCTION_TYPE_NOP:
      pass
    elif data["type"] == ECM_TX_INSTRUCTION_TYPE_DDS_SETUP_BPSK:
      r |= (data["dds_lfsr_phase_inc"] << 16)
    elif data["type"] == ECM_TX_INSTRUCTION_TYPE_DDS_SETUP_CW_SWEEP:
      r |= (data["dds_sin_sweep_phase_inc_start"] << 16)
      r |= (data["dds_sin_sweep_phase_inc_stop"] << 32)
      r |= (data["dds_sin_sweep_phase_inc_step"] << 48)
    elif data["type"] == ECM_TX_INSTRUCTION_TYPE_DDS_SETUP_CW_STEP:
      r |= (data["dds_sin_step_phase_inc_min"] << 16)
      r |= (data["dds_sin_step_phase_inc_rand_offset_mask"] << 32)
      r |= (data["dds_sin_step_period_minus_one"] << 48)
    elif data["type"] == ECM_TX_INSTRUCTION_TYPE_PLAYBACK:
      r |= (data["playback_mode"] << 16)
      r |= (data["playback_base_count"] << 32)
      r |= (data["playback_rand_offset_mask"] << 48)
    elif data["type"] == ECM_TX_INSTRUCTION_TYPE_WAIT:
      r |= (data["wait_base_duration"] << 16)
      r |= (data["wait_rand_offset_mask"] << 40)
    elif data["type"] == ECM_TX_INSTRUCTION_TYPE_JUMP:
      r |= (data["jump_target_address"] << 16)
      r |= (data["jump_counter_check"] << 32)
      r |= (data["jump_counter_value"] << 40)
    else:
      raise RuntimeError("invalid instruction type")

    return r

  def _pack_tx_instruction_header(self, data):
    r = 0

    r |= (data["valid"] << 3)
    r |= data["type"]

    r |= (data["header_output_valid"] << 7)
    r |= (data["header_output_control"] << 4)

    r |= (data["header_dds_valid"] << 11)
    r |= (data["header_dds_sin_phase_inc_sel"] << 8)
    r |= (data["header_dds_output_sel"] << 9)

    return r