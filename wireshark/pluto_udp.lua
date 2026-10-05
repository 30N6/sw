-- pluto_udp.lua
-- Pluto UDP: 4-byte big-endian sequence number, then arbitrary payload.
-- Gaps are tracked per direction and flagged like TCP "previous segment not captured".

local proto = Proto("pluto_udp", "Pluto UDP")

local f_seq      = ProtoField.uint32("pluto_udp.seq", "Sequence Number", base.DEC)
local f_data     = ProtoField.bytes("pluto_udp.data", "Data")
local f_data_len = ProtoField.uint32("pluto_udp.data_len", "Data Length", base.DEC)
local f_missing  = ProtoField.uint32("pluto_udp.analysis.missing", "Missing Segments", base.DEC)
local f_lost     = ProtoField.bool("pluto_udp.analysis.lost_segment", "Previous segment not captured", base.NONE)
local f_retrans  = ProtoField.bool("pluto_udp.analysis.retransmission", "Retransmission", base.NONE)

local ef_gap = ProtoExpert.new(
    "pluto_udp.seq_gap",
    "Previous segment not captured",
    expert.group.SEQUENCE,
    expert.severity.WARN)
local ef_retrans = ProtoExpert.new(
    "pluto_udp.retransmission",
    "Retransmission or duplicate sequence number",
    expert.group.SEQUENCE,
    expert.severity.NOTE)

proto.fields  = { f_seq, f_data, f_data_len, f_missing, f_lost, f_retrans }
proto.experts = { ef_gap, ef_retrans }
proto.prefs.port = Pref.uint("UDP port", 12345, "UDP port for Pluto UDP")

local SEQ_LEN = 4
local MOD = 0x100000000

-- Signed 32-bit distance a - b, so wraparound still compares correctly.
local function seq_delta(a, b)
    local d = (a - b) % MOD
    if d >= 0x80000000 then
        d = d - MOD
    end
    return d
end

local conversations = {}  -- key -> { next = expected seq }
local packet_state = {}   -- pinfo.number -> analysis result

local function flow_key(pinfo)
    return tostring(pinfo.src) .. ":" .. pinfo.src_port
        .. "->" .. tostring(pinfo.dst) .. ":" .. pinfo.dst_port
end

local function analyze(pinfo, seq)
    local key = flow_key(pinfo)
    local conv = conversations[key]
    if not conv then
        conv = {}
        conversations[key] = conv
    end

    if conv.next == nil then
        conv.next = (seq + 1) % MOD
        return { kind = "first", seq = seq }
    end

    local delta = seq_delta(seq, conv.next)
    if delta == 0 then
        conv.next = (seq + 1) % MOD
        return { kind = "ok", seq = seq }
    elseif delta > 0 then
        local missing = delta
        conv.next = (seq + 1) % MOD
        return { kind = "gap", seq = seq, missing = missing }
    else
        return { kind = "retrans", seq = seq }
    end
end

function proto.dissector(buffer, pinfo, tree)
    local len = buffer:len()
    if len < SEQ_LEN then
        return 0
    end

    local seq = buffer(0, SEQ_LEN):uint()

    -- First pass only: later passes (packet clicks, retaps) must reuse this.
    if not pinfo.visited then
        packet_state[pinfo.number] = analyze(pinfo, seq)
    end
    local st = packet_state[pinfo.number] or { kind = "ok", seq = seq }

    pinfo.cols.protocol = "PLUTO_UDP"

    local subtree = tree:add(proto, buffer(), "Pluto UDP")
    local seq_item = subtree:add(f_seq, buffer(0, SEQ_LEN))

    local data_len = len - SEQ_LEN
    subtree:add(f_data_len, data_len):set_generated()
    if data_len > 0 then
        subtree:add(f_data, buffer(SEQ_LEN, data_len))
    end

    local info = string.format("Seq=%u Len=%d", seq, data_len)

    if st.kind == "gap" then
        seq_item:add_expert_info(ef_gap,
            string.format("Previous segment not captured (%u missing)", st.missing))
        subtree:add(f_missing, st.missing):set_generated()
        subtree:add(f_lost, true):set_generated()
        info = info .. string.format(" [Previous segment not captured, %u missing]", st.missing)
    elseif st.kind == "retrans" then
        seq_item:add_expert_info(ef_retrans)
        subtree:add(f_retrans, true):set_generated()
        info = info .. " [Retransmission]"
    end

    pinfo.cols.info = info
    return len
end

local port_table = DissectorTable.get("udp.port")
local registered_port = 0

function proto.init()
    conversations = {}
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
