-- pluto_udp.lua
-- Report: UDP seq (4, big-endian) + intercept header (16, little-endian) + body.
-- Control: intercept header begins at offset 0 (no UDP sequence).
-- Offset 10 of the header is message type, offset 11 is module id.
-- UDP sequence space: per direction, reports only.
-- Message sequence space: per direction and module id.
-- 64-bit timestamps are upper word, then lower word. UInt64() takes (lower, upper).

local proto = Proto("pluto_udp", "Pluto UDP")

local MAGIC_CONTROL = 0x494E5443  -- wire LE bytes 43 54 4E 49
local MAGIC_REPORT  = 0x494E5452  -- wire LE bytes 52 54 4E 49
local HDR_LEN       = 16
local SEQ_LEN       = 4
local MOD           = 0x100000000

local magic_vals = {
    [MAGIC_CONTROL] = "CONTROL (INTC)",
    [MAGIC_REPORT]  = "REPORT (INTR)",
}
local module_vals = {
    [0x00] = "CONTROL",
    [0x01] = "DWELL_CONTROLLER",
    [0x02] = "DWELL_STATS",
    [0x03] = "STREAM_ENCODER",
    [0x07] = "STATUS",
}
local control_type_vals = {
    [0x00] = "ENABLE",
    [0x01] = "DWELL_CONTROLLER_CONFIG",
    [0x02] = "CHANNEL_CONFIG",
    [0x03] = "STREAM_CONFIG",
}
local report_type_vals = {
    [0x10] = "DWELL_STATS",
    [0x20] = "STREAM",
    [0x30] = "STATUS",
}

local f_seq      = ProtoField.uint32("pluto_udp.seq", "UDP Sequence Number", base.DEC)
local f_magic    = ProtoField.uint32("pluto_udp.magic", "Magic", base.HEX, magic_vals)
local f_msg_seq  = ProtoField.uint32("pluto_udp.msg_seq", "Message Sequence Number", base.DEC)
local f_addr     = ProtoField.uint16("pluto_udp.address", "Address", base.HEX)
local f_msg_type = ProtoField.uint8("pluto_udp.msg_type", "Message Type", base.HEX)
local f_module   = ProtoField.uint8("pluto_udp.module_id", "Module ID", base.HEX, module_vals)
local f_reset    = ProtoField.uint8("pluto_udp.reset", "Reset", base.DEC)
local f_en0      = ProtoField.uint8("pluto_udp.enable_0", "Enable 0", base.DEC)
local f_en1      = ProtoField.uint8("pluto_udp.enable_1", "Enable 1", base.DEC)
local f_en2      = ProtoField.uint8("pluto_udp.enable_2", "Enable 2", base.DEC)
local f_dwell_en = ProtoField.uint8("pluto_udp.dwell.enable", "Enable", base.DEC)
local f_dwell_tag = ProtoField.uint16("pluto_udp.dwell.tag", "Tag", base.DEC)
local f_dwell_freq = ProtoField.uint32("pluto_udp.dwell.frequency", "Frequency", base.DEC)
local f_dwell_win = ProtoField.uint32("pluto_udp.dwell.window_duration", "Window Duration", base.DEC)
local f_chan_en = ProtoField.uint8("pluto_udp.channel.enable", "Enable", base.DEC)
local f_chan_force = ProtoField.uint8("pluto_udp.channel.force_trigger", "Force Trigger", base.DEC)
local f_chan_stream = ProtoField.uint8("pluto_udp.channel.force_stream_index", "Force Stream Index", base.DEC)
local f_chan_tag = ProtoField.uint16("pluto_udp.channel.tag", "Tag", base.DEC)
local f_chan_start = ProtoField.uint32("pluto_udp.channel.threshold_start", "Threshold Start", base.DEC)
local f_chan_cont = ProtoField.uint32("pluto_udp.channel.threshold_continue", "Threshold Continue", base.DEC)
local f_chan_coast = ProtoField.uint32("pluto_udp.channel.coast_cycles", "Coast Cycles", base.DEC)
local f_chan_integ = ProtoField.uint32("pluto_udp.channel.integration_cycles", "Integration Cycles", base.DEC)
local f_stream_en = ProtoField.uint8("pluto_udp.stream.enable", "Enable", base.DEC)
local f_stream_tag = ProtoField.uint16("pluto_udp.stream.tag", "Tag", base.DEC)
local f_st_enables = ProtoField.uint32("pluto_udp.status.enables", "Enables", base.HEX)
local f_st_flags = ProtoField.uint32("pluto_udp.status.flags", "Status Flags", base.HEX)
local f_st_reporter = ProtoField.uint32("pluto_udp.status.reporter_flags", "Reporter Flags", base.HEX)
local f_st_ts_hi = ProtoField.uint32("pluto_udp.status.timestamp_hi", "Timestamp Upper", base.DEC)
local f_st_ts_lo = ProtoField.uint32("pluto_udp.status.timestamp_lo", "Timestamp Lower", base.DEC)
local f_st_ts = ProtoField.uint64("pluto_udp.status.timestamp", "Timestamp", base.DEC)
local f_ds_seq = ProtoField.uint32("pluto_udp.dwell_stats.seq", "Dwell Sequence Number", base.DEC)
local f_ds_freq = ProtoField.uint32("pluto_udp.dwell_stats.frequency", "Frequency", base.DEC)
local f_ds_tag = ProtoField.uint16("pluto_udp.dwell_stats.tag", "Tag", base.DEC)
local f_ds_win = ProtoField.uint16("pluto_udp.dwell_stats.window_duration", "Window Duration", base.DEC)
local f_ds_wseq = ProtoField.uint32("pluto_udp.dwell_stats.window_seq", "Window Sequence Number", base.DEC)
local f_ds_ts_hi = ProtoField.uint32("pluto_udp.dwell_stats.timestamp_hi", "Window Timestamp Upper", base.DEC)
local f_ds_ts_lo = ProtoField.uint32("pluto_udp.dwell_stats.timestamp_lo", "Window Timestamp Lower", base.DEC)
local f_ds_ts = ProtoField.uint64("pluto_udp.dwell_stats.timestamp", "Window Timestamp", base.DEC)
local f_de_valid = ProtoField.uint8("pluto_udp.dwell_entry.valid", "Valid", base.DEC)
local f_de_index = ProtoField.uint16("pluto_udp.dwell_entry.index", "Index", base.DEC)
local f_de_acc0 = ProtoField.uint32("pluto_udp.dwell_entry.accum0", "Accum 0", base.DEC)
local f_de_acc1 = ProtoField.uint32("pluto_udp.dwell_entry.accum1", "Accum 1", base.DEC)
local f_de_max = ProtoField.uint32("pluto_udp.dwell_entry.max", "Max", base.DEC)
local f_sh_seq = ProtoField.uint32("pluto_udp.stream.seq", "Dwell Sequence Number", base.DEC)
local f_sh_freq = ProtoField.uint32("pluto_udp.stream.frequency", "Frequency", base.DEC)
local f_sh_tag = ProtoField.uint16("pluto_udp.stream.dwell_tag", "Tag", base.DEC)
local f_sh_win = ProtoField.uint16("pluto_udp.stream.window_duration", "Window Duration", base.DEC)
local f_sh_ts_hi = ProtoField.uint32("pluto_udp.stream.timestamp_hi", "Window Timestamp Upper", base.DEC)
local f_sh_ts_lo = ProtoField.uint32("pluto_udp.stream.timestamp_lo", "Window Timestamp Lower", base.DEC)
local f_sh_ts = ProtoField.uint64("pluto_udp.stream.timestamp", "Window Timestamp", base.DEC)
local f_ss_trig = ProtoField.uint8("pluto_udp.sample.trigger_type", "Trigger Type", base.DEC)
local f_ss_stream = ProtoField.uint8("pluto_udp.sample.stream_index", "Stream Index", base.DEC)
local f_ss_chan = ProtoField.uint16("pluto_udp.sample.channel_index", "Channel Index", base.DEC)
local f_ss_index = ProtoField.uint32("pluto_udp.sample.sample_index", "Sample Index", base.DEC)
local f_ss_i = ProtoField.int32("pluto_udp.sample.i", "I", base.DEC)
local f_ss_q = ProtoField.int32("pluto_udp.sample.q", "Q", base.DEC)
local f_payload  = ProtoField.bytes("pluto_udp.payload", "Payload")
local f_missing  = ProtoField.uint32("pluto_udp.analysis.missing", "Missing UDP Segments", base.DEC)
local f_lost     = ProtoField.bool("pluto_udp.analysis.lost_segment", "Previous UDP segment not captured", base.NONE)
local f_retrans  = ProtoField.bool("pluto_udp.analysis.retransmission", "UDP retransmission", base.NONE)
local f_msg_missing = ProtoField.uint32("pluto_udp.analysis.msg_missing", "Missing Messages", base.DEC)
local f_msg_lost    = ProtoField.bool("pluto_udp.analysis.msg_lost_segment", "Previous message not captured", base.NONE)
local f_msg_retrans = ProtoField.bool("pluto_udp.analysis.msg_retransmission", "Message retransmission", base.NONE)

local ef_gap = ProtoExpert.new("pluto_udp.seq_gap", "Previous segment not captured",
    expert.group.SEQUENCE, expert.severity.WARN)
local ef_retrans = ProtoExpert.new("pluto_udp.retransmission", "Retransmission or duplicate sequence number",
    expert.group.SEQUENCE, expert.severity.NOTE)
local ef_msg_gap = ProtoExpert.new("pluto_udp.msg_seq_gap", "Previous message not captured",
    expert.group.SEQUENCE, expert.severity.WARN)
local ef_msg_retrans = ProtoExpert.new("pluto_udp.msg_retransmission", "Retransmission or duplicate message sequence number",
    expert.group.SEQUENCE, expert.severity.NOTE)
local ef_magic = ProtoExpert.new("pluto_udp.bad_magic", "Unknown magic number",
    expert.group.MALFORMED, expert.severity.ERROR)
local ef_short = ProtoExpert.new("pluto_udp.short_header", "Truncated intercept header",
    expert.group.MALFORMED, expert.severity.ERROR)

proto.fields  = {
    f_seq, f_magic, f_msg_seq, f_addr, f_msg_type, f_module,
    f_reset, f_en0, f_en1, f_en2,
    f_dwell_en, f_dwell_tag, f_dwell_freq, f_dwell_win,
    f_chan_en, f_chan_force, f_chan_stream, f_chan_tag,
    f_chan_start, f_chan_cont, f_chan_coast, f_chan_integ,
    f_stream_en, f_stream_tag,
    f_st_enables, f_st_flags, f_st_reporter, f_st_ts_hi, f_st_ts_lo, f_st_ts,
    f_ds_seq, f_ds_freq, f_ds_tag, f_ds_win, f_ds_wseq, f_ds_ts_hi, f_ds_ts_lo, f_ds_ts,
    f_de_valid, f_de_index, f_de_acc0, f_de_acc1, f_de_max,
    f_sh_seq, f_sh_freq, f_sh_tag, f_sh_win, f_sh_ts_hi, f_sh_ts_lo, f_sh_ts,
    f_ss_trig, f_ss_stream, f_ss_chan, f_ss_index, f_ss_i, f_ss_q,
    f_payload,
    f_missing, f_lost, f_retrans, f_msg_missing, f_msg_lost, f_msg_retrans,
}
proto.experts = { ef_gap, ef_retrans, ef_msg_gap, ef_msg_retrans, ef_magic, ef_short }
proto.prefs.port = Pref.uint("UDP port", 12345, "UDP port for Pluto UDP")

local function seq_delta(a, b)
    local d = (a - b) % MOD
    if d >= 0x80000000 then d = d - MOD end
    return d
end

local udp_convs = {}
local msg_convs = {}
local packet_state = {}

local function flow_key(pinfo)
    return tostring(pinfo.src) .. ":" .. pinfo.src_port
        .. "->" .. tostring(pinfo.dst) .. ":" .. pinfo.dst_port
end

local function analyze(convs, key, seq)
    local conv = convs[key]
    if not conv then
        conv = {}
        convs[key] = conv
    end
    if conv.next == nil then
        conv.next = (seq + 1) % MOD
        return { kind = "first" }
    end
    local delta = seq_delta(seq, conv.next)
    if delta == 0 then
        conv.next = (seq + 1) % MOD
        return { kind = "ok" }
    elseif delta > 0 then
        conv.next = (seq + 1) % MOD
        return { kind = "gap", missing = delta }
    end
    return { kind = "retrans" }
end

local function msg_type_name(magic, msg_type)
    local t = (magic == MAGIC_CONTROL) and control_type_vals or report_type_vals
    return t[msg_type] or string.format("0x%02x", msg_type)
end

-- range is upper word, then lower word. UInt64's constructor is (lower, upper).
local function add_timestamp(tree, range, hi_field, lo_field, ts_field)
    local hi = range(0, 4):le_uint()
    local lo = range(4, 4):le_uint()
    tree:add_le(hi_field, range(0, 4))
    tree:add_le(lo_field, range(4, 4))
    local ts = UInt64(lo, hi)
    tree:add(ts_field, range, ts):set_generated()
    return ts
end

function proto.dissector(buffer, pinfo, tree)
    local len = buffer:len()
    if len < 4 then return 0 end

    local is_control = buffer(0, 4):le_uint() == MAGIC_CONTROL
    local seq_len = is_control and 0 or SEQ_LEN
    if len < seq_len then return 0 end

    local seq
    if seq_len > 0 then
        seq = buffer(0, SEQ_LEN):uint()
    end

    local has_hdr = len >= seq_len + HDR_LEN
    local msg_seq, magic, module_id
    if has_hdr then
        magic = buffer(seq_len, 4):le_uint()
        msg_seq = buffer(seq_len + 4, 4):le_uint()
        module_id = buffer(seq_len + 11, 1):uint()
    end

    if not pinfo.visited then
        local st = {}
        if seq ~= nil then
            st.udp = analyze(udp_convs, flow_key(pinfo), seq)
        end
        if has_hdr then
            st.msg = analyze(msg_convs, flow_key(pinfo) .. ":" .. module_id, msg_seq)
        end
        packet_state[pinfo.number] = st
    end
    local st = packet_state[pinfo.number] or {}

    pinfo.cols.protocol = "PLUTO_UDP"
    local subtree = tree:add(proto, buffer(), "Pluto UDP")

    local info = ""
    if seq ~= nil then
        local seq_item = subtree:add(f_seq, buffer(0, SEQ_LEN))
        info = string.format("Seq=%u", seq)
        local ust = st.udp or { kind = "ok" }
        if ust.kind == "gap" then
            seq_item:add_proto_expert_info(ef_gap,
                string.format("Previous segment not captured (%u missing)", ust.missing))
            subtree:add(f_missing, ust.missing):set_generated()
            subtree:add(f_lost, true):set_generated()
            info = info .. string.format(" [Previous segment not captured, %u missing]", ust.missing)
        elseif ust.kind == "retrans" then
            seq_item:add_proto_expert_info(ef_retrans)
            subtree:add(f_retrans, true):set_generated()
            info = info .. " [Retransmission]"
        end
    end

    if not has_hdr then
        subtree:add_proto_expert_info(ef_short)
        pinfo.cols.info = info .. " [truncated]"
        return len
    end

    local hdr = buffer(seq_len, HDR_LEN)
    local htree = subtree:add(proto, hdr, "Intercept Header")
    local magic_item = htree:add_le(f_magic, hdr(0, 4))
    local msg_item = htree:add_le(f_msg_seq, hdr(4, 4))

    local mst = st.msg or { kind = "ok" }
    if mst.kind == "gap" then
        msg_item:add_proto_expert_info(ef_msg_gap,
            string.format("Previous message not captured (%u missing)", mst.missing))
        subtree:add(f_msg_missing, mst.missing):set_generated()
        subtree:add(f_msg_lost, true):set_generated()
        info = info .. string.format(" [Previous message not captured, %u missing]", mst.missing)
    elseif mst.kind == "retrans" then
        msg_item:add_proto_expert_info(ef_msg_retrans)
        subtree:add(f_msg_retrans, true):set_generated()
        info = info .. " [Message retransmission]"
    end

    if is_control then
        htree:add_le(f_addr, hdr(8, 2))
    else
        htree:add(buffer(seq_len + 8, 2), "Padding: " .. hdr(8, 2):bytes():tohex())
    end

    local msg_type = hdr(10, 1):uint()
    local type_item = htree:add(f_msg_type, hdr(10, 1))
    type_item:append_text(" (" .. msg_type_name(magic, msg_type) .. ")")
    htree:add(f_module, hdr(11, 1))
    htree:add(hdr(12, 4), "Padding: " .. hdr(12, 4):bytes():tohex())

    if magic ~= MAGIC_CONTROL and magic ~= MAGIC_REPORT then
        magic_item:add_proto_expert_info(ef_magic, string.format("0x%08x", magic))
    end

    local body_off = seq_len + HDR_LEN
    local kind = is_control and "CONTROL" or (magic == MAGIC_REPORT and "REPORT" or "UNKNOWN")
    info = info .. string.format(" MsgSeq=%u %s %s %s", msg_seq, kind,
        msg_type_name(magic, msg_type),
        module_vals[module_id] or string.format("mod=0x%02x", module_id))
    if is_control then
        info = info .. string.format(" addr=0x%04x", hdr(8, 2):le_uint())
    end

    if is_control and msg_type == 0x00 and len >= body_off + 8 then
        local body = buffer(body_off, 8)
        local btree = subtree:add(proto, body, "Enable Control")
        btree:add(f_reset, body(0, 1))
        btree:add(f_en0, body(1, 1))
        btree:add(f_en1, body(2, 1))
        btree:add(f_en2, body(3, 1))
        btree:add(body(4, 4), "Padding: " .. body(4, 4):bytes():tohex())
        info = info .. string.format(" reset=%u en=%u,%u,%u",
            body(0, 1):uint(), body(1, 1):uint(), body(2, 1):uint(), body(3, 1):uint())
        body_off = body_off + 8
    elseif is_control and msg_type == 0x01 and len >= body_off + 16 then
        local body = buffer(body_off, 16)
        local btree = subtree:add(proto, body, "Dwell Controller Config")
        btree:add(f_dwell_en, body(0, 1))
        btree:add(body(1, 1), "Padding: " .. body(1, 1):bytes():tohex())
        btree:add_le(f_dwell_tag, body(2, 2))
        btree:add_le(f_dwell_freq, body(4, 4))
        btree:add_le(f_dwell_win, body(8, 4))
        btree:add(body(12, 4), "Padding: " .. body(12, 4):bytes():tohex())
        info = info .. string.format(" en=%u tag=%u freq=%u win=%u",
            body(0, 1):uint(), body(2, 2):le_uint(), body(4, 4):le_uint(), body(8, 4):le_uint())
        body_off = body_off + 16
    elseif is_control and msg_type == 0x02 and len >= body_off + 24 then
        local body = buffer(body_off, 24)
        local btree = subtree:add(proto, body, "Channel Config")
        btree:add(f_chan_en, body(0, 1))
        btree:add(f_chan_force, body(1, 1))
        btree:add(f_chan_stream, body(2, 1))
        btree:add(body(3, 1), "Padding: " .. body(3, 1):bytes():tohex())
        btree:add_le(f_chan_tag, body(4, 2))
        btree:add(body(6, 2), "Padding: " .. body(6, 2):bytes():tohex())
        btree:add_le(f_chan_start, body(8, 4))
        btree:add_le(f_chan_cont, body(12, 4))
        btree:add_le(f_chan_coast, body(16, 4))
        btree:add_le(f_chan_integ, body(20, 4))
        info = info .. string.format(" en=%u force=%u stream=%u tag=%u start=%u cont=%u coast=%u integ=%u",
            body(0, 1):uint(), body(1, 1):uint(), body(2, 1):uint(), body(4, 2):le_uint(),
            body(8, 4):le_uint(), body(12, 4):le_uint(), body(16, 4):le_uint(), body(20, 4):le_uint())
        body_off = body_off + 24
    elseif is_control and msg_type == 0x03 and len >= body_off + 8 then
        local body = buffer(body_off, 8)
        local btree = subtree:add(proto, body, "Stream Config")
        btree:add(f_stream_en, body(0, 1))
        btree:add(body(1, 1), "Padding: " .. body(1, 1):bytes():tohex())
        btree:add_le(f_stream_tag, body(2, 2))
        btree:add(body(4, 4), "Padding: " .. body(4, 4):bytes():tohex())
        info = info .. string.format(" en=%u tag=%u", body(0, 1):uint(), body(2, 2):le_uint())
        body_off = body_off + 8
    elseif magic == MAGIC_REPORT and msg_type == 0x30 and len >= body_off + 20 then
        local body = buffer(body_off, 20)
        local btree = subtree:add(proto, body, "Status Report")
        local enables = body(0, 4):le_uint()
        local flags = body(4, 4):le_uint()
        local reporter = body(8, 4):le_uint()
        btree:add_le(f_st_enables, body(0, 4))
        btree:add_le(f_st_flags, body(4, 4))
        btree:add_le(f_st_reporter, body(8, 4))
        local ts = add_timestamp(btree, body(12, 8), f_st_ts_hi, f_st_ts_lo, f_st_ts)
        info = info .. string.format(" enables=0x%08x flags=0x%08x reporter=0x%08x ts=%s",
            enables, flags, reporter, tostring(ts))
        body_off = body_off + 20
    elseif magic == MAGIC_REPORT and msg_type == 0x10 and len >= body_off + 24 then
        local body = buffer(body_off, 24)
        local btree = subtree:add(proto, body, "Dwell Stats Header")
        btree:add_le(f_ds_seq, body(0, 4))
        btree:add_le(f_ds_freq, body(4, 4))
        btree:add_le(f_ds_tag, body(8, 2))
        btree:add_le(f_ds_win, body(10, 2))
        btree:add_le(f_ds_wseq, body(12, 4))
        add_timestamp(btree, body(16, 8), f_ds_ts_hi, f_ds_ts_lo, f_ds_ts)
        info = info .. string.format(" dwell=%u freq=%u tag=%u win=%u wseq=%u",
            body(0, 4):le_uint(), body(4, 4):le_uint(), body(8, 2):le_uint(),
            body(10, 2):le_uint(), body(12, 4):le_uint())
        body_off = body_off + 24
        local n = 0
        while len - body_off >= 16 do
            local ent = buffer(body_off, 16)
            local etree = subtree:add(proto, ent, string.format("Dwell Entry %d", n))
            etree:add(f_de_valid, ent(0, 1))
            etree:add(ent(1, 1), "Padding: " .. ent(1, 1):bytes():tohex())
            etree:add_le(f_de_index, ent(2, 2))
            etree:add_le(f_de_acc0, ent(4, 4))
            etree:add_le(f_de_acc1, ent(8, 4))
            etree:add_le(f_de_max, ent(12, 4))
            etree:append_text(string.format(": valid=%u index=%u max=%u",
                ent(0, 1):uint(), ent(2, 2):le_uint(), ent(12, 4):le_uint()))
            body_off = body_off + 16
            n = n + 1
        end
        info = info .. string.format(" entries=%u", n)
    elseif magic == MAGIC_REPORT and msg_type == 0x20 and len >= body_off + 24 then
        local body = buffer(body_off, 24)
        local btree = subtree:add(proto, body, "Stream Header")
        btree:add_le(f_sh_seq, body(0, 4))
        btree:add_le(f_sh_freq, body(4, 4))
        btree:add_le(f_sh_tag, body(8, 2))
        btree:add_le(f_sh_win, body(10, 2))
        btree:add(body(12, 4), "Padding: " .. body(12, 4):bytes():tohex())
        add_timestamp(btree, body(16, 8), f_sh_ts_hi, f_sh_ts_lo, f_sh_ts)
        info = info .. string.format(" dwell=%u freq=%u tag=%u win=%u",
            body(0, 4):le_uint(), body(4, 4):le_uint(), body(8, 2):le_uint(), body(10, 2):le_uint())
        body_off = body_off + 24
        local n = 0
        while len - body_off >= 16 do
            local ent = buffer(body_off, 16)
            local etree = subtree:add(proto, ent, string.format("Stream Sample %d", n))
            etree:add(f_ss_trig, ent(0, 1))
            etree:add(f_ss_stream, ent(1, 1))
            etree:add_le(f_ss_chan, ent(2, 2))
            etree:add_le(f_ss_index, ent(4, 4))
            etree:add_le(f_ss_i, ent(8, 4))
            etree:add_le(f_ss_q, ent(12, 4))
            etree:append_text(string.format(": trig=%u stream=%u ch=%u idx=%u I=%d Q=%d",
                ent(0, 1):uint(), ent(1, 1):uint(), ent(2, 2):le_uint(),
                ent(4, 4):le_uint(), ent(8, 4):le_int(), ent(12, 4):le_int()))
            body_off = body_off + 16
            n = n + 1
        end
        info = info .. string.format(" samples=%u", n)
    end

    if len > body_off then
        subtree:add(f_payload, buffer(body_off))
    end

    pinfo.cols.info = info
    return len
end

local port_table = DissectorTable.get("udp.port")
local registered_port = 0

function proto.init()
    udp_convs = {}
    msg_convs = {}
    packet_state = {}
    if registered_port ~= 0 then
        port_table:remove(registered_port, proto)
        registered_port = 0
    end
    local port = proto.prefs.port
    if port ~= 0 then
        port_table:add(port, proto)
        registered_port = port
    end
end
