// Hookshot native engine: the key-0xa0 draw function's entries, in place (hl/bridge/LoopBridge.h).
#include "hl/bridge/LoopBridge.h"

#include <cstring>

#include "hl/bridge/GfxBridge.h"

namespace hl::bridge {

namespace {
// GOT slots of the game: the global switch's pointer (its u32 set: the commands are written into the command memory
// instead of called), the method the model's class has in the common case (compared with its vtable's +488), and the
// sub-mesh submission method the drawable's class has in the common case (compared with its vtable's +0x58)
constexpr GuestAddr kSwitchSlot = 0x84ca2dd8;
constexpr GuestAddr kModelMethodSlot = 0x84ca30f8;
constexpr GuestAddr kSubmitMethodSlot = 0x84cb5dc0;

// The block's fields the function reads and writes (the render-state block of gfx-record-job.md section 8)
constexpr uint64_t kBlockContext = 40, kBlockPass = 56, kBlockGeometry = 59, kBlockMode = 92, kBlockKeyApplied = 90,
                   kBlockEnableApplied = 91, kBlockTriangles = 80, kBlockFrame = 76, kBlockMask = 104,
                   kBlockQuery = 192, kBlockQueryIndex = 200;

struct Mem {
    GuestRuntime& rt;
    template <class T>
    T rd(GuestAddr a) const {
        T v;
        std::memcpy(&v, rt.ptr(a), sizeof v);
        return v;
    }
    template <class T>
    void wr(GuestAddr a, T v) const {
        std::memcpy(rt.ptr(a), &v, sizeof v);
        rt.written(a, sizeof v);
    }
    bool inline_write() const { return rd<uint32_t>(rd<uint64_t>(kSwitchSlot)) != 0; }
};

// The material's state callback is the game's empty function (the render-state function then calls no guest code)
bool state_callback_empty(const Mem& m, GuestAddr block) {
    const GuestAddr material = m.rd<uint64_t>(block + offsetof(guest::RenderStateBlock, material));
    if (!material) return false;
    const GuestAddr callback = m.rd<uint64_t>(material + offsetof(guest::Material, state_callback));
    return callback && m.rd<uint64_t>(callback + offsetof(guest::StateCallback, invoke)) == m.rd<uint64_t>(kEmptyFunctionSlot);
}
}   // namespace

const char* entry_way_name(EntryWay way) {
    static constexpr const char* names[] = {"native",     "masked",   "enable",    "state",     "model",
                                            "inline",     "method",    "geometry",  "flags",     "bit5",
                                            "indirect",   "cl-other", "cl-cull",    "cl-plain",
                                            "instances", "norecorded", "nolist"};
    static_assert(sizeof names / sizeof names[0] == (size_t)EntryWay::Count);
    return (size_t)way < (size_t)EntryWay::Count ? names[(size_t)way] : "?";
}

EntryWay KeyLoopBridge::classify(const KeyLoopCall& call, GuestAddr entry, KeyLoopEntry& plan) const {
    const Mem m{runtime_};
    const GuestAddr block = call.block;
    const uint32_t kind = m.rd<uint32_t>(entry + 8);
    if (!(kind & (uint32_t)call.mask)) return EntryWay::Masked;
    const uint16_t h = m.rd<uint16_t>(entry + 14);
    // (the render enable and the render state change before the entry's draw; both are applied by run(), which reads
    // the block again between them: the enable function rewrites the state key and the mode bits)
    const bool enable_changes = ((h >> 4) & 1u) != (uint32_t)(int32_t)m.rd<int8_t>(block + kBlockEnableApplied);
    const uint32_t block_mask = m.rd<uint32_t>(block + kBlockMask);
    bool state_may_change = enable_changes;
    if (!state_may_change) {
        if ((block_mask & kind) && ((h >> 10) & 1))
            state_may_change = true;   // (the key takes the block's mode bit 19)
        else
            state_may_change = m.rd<uint8_t>(block + kBlockKeyApplied) != (uint8_t)((h & 0xf) | ((block_mask & kind) ? 0x80 : 0));
    }
    if (state_may_change && !state_callback_empty(m, block)) return EntryWay::StateChange;
    if (enable_changes && m.rd<uint64_t>(block + kBlockQuery) != 0 && m.inline_write()) return EntryWay::EnableChange;

    plan = KeyLoopEntry{};
    plan.entry = entry;
    plan.bits = h;
    plan.kind = kind;
    plan.enable_changes = enable_changes;
    plan.drawable = m.rd<uint64_t>(entry + 16);
    const GuestAddr drawable = plan.drawable;
    plan.pass = m.rd<uint8_t>(block + kBlockPass);
    plan.model = m.rd<uint64_t>(drawable + 8);
    const GuestAddr model = plan.model;
    const GuestAddr passes = m.rd<uint64_t>(model + 64) + ((uint64_t)plan.pass << 8);
    plan.query = m.rd<uint64_t>(passes + 104);
    if (m.rd<uint64_t>(m.rd<uint64_t>(model) + 488) != m.rd<uint64_t>(kModelMethodSlot)) return EntryWay::ModelClass;
    plan.base = m.rd<uint32_t>(passes + 120);
    plan.index = (uint32_t)(m.rd<uint16_t>(drawable + 24) + (uint32_t)m.rd<uint16_t>(model + 244) * plan.pass);
    plan.reset = plan.query && m.rd<uint64_t>(model + 72) == 0;
    const bool conditional = (block_mask & kind) != 0;
    if (plan.reset && m.inline_write()) return EntryWay::InlineWrite;
    if (conditional) {
        uint64_t last = m.rd<uint64_t>(block + kBlockQuery);
        uint32_t last_index = m.rd<uint32_t>(block + kBlockQueryIndex);
        if (enable_changes && !(last == 0 && last_index == 0)) last = 0, last_index = 0xffffffffu;   // (the enable function resets the pair)
        if (!(plan.query == last && plan.index == last_index)) {
            if (m.inline_write()) return EntryWay::InlineWrite;
            plan.conditional = plan.query != 0;
            plan.no_query = plan.query == 0;
            plan.was_conditional = last != 0;
        }
    }
    plan.sub_mesh = (h >> 6) & 0xf;
    plan.method = m.rd<uint64_t>(m.rd<uint64_t>(drawable) + 88);
    if (plan.method != m.rd<uint64_t>(kSubmitMethodSlot)) return EntryWay::Method;
    plan.in_range = plan.sub_mesh < ((m.rd<uint16_t>(drawable + 30) >> 4) & 0xfu);
    if (plan.in_range) {
        plan.resource = m.rd<uint64_t>(drawable + 104);
        const GuestAddr resource = plan.resource;
        if (m.rd<uint8_t>(resource + 1694) != m.rd<uint8_t>(block + kBlockGeometry)) return EntryWay::Geometry;
        const uint32_t drawn = m.rd<uint32_t>(drawable + 84);
        if ((call.flags & 8u) & drawn) return EntryWay::FlagsMask;
        if ((drawn >> 5) & 1) return EntryWay::FlagsBit5;
        if (const uint32_t kinds = drawn & call.flags; kinds & 0x51u) {
            if (kinds & 0x10u) return EntryWay::Indirect;
            const GuestAddr clusters = m.rd<uint64_t>(drawable + 120);
            if ((kinds & 2u) && clusters) {
                const GuestAddr cluster = clusters + (uint64_t)m.rd<uint8_t>(block + kBlockPass) * 24;
                if (m.rd<int8_t>(cluster + 16) == (int32_t)plan.sub_mesh) {
                    // (this sub-mesh's cluster entry: a list of records, each a run of index ranges of one descriptor)
                    if (m.rd<uint64_t>(cluster + 8) != 0) return EntryWay::ClusterOther;
                    plan.cluster_list = m.rd<uint64_t>(cluster);
                    plan.command_buffer = m.rd<uint64_t>(m.rd<uint64_t>(block + kBlockContext) + 216);
                    return EntryWay::Native;
                }
            }
            return (kinds & 0x80u) ? EntryWay::ClusterCull : EntryWay::ClusterPlain;
        }
        if (m.rd<uint16_t>(drawable + 92) > 1) return EntryWay::Instances;
        plan.record = m.rd<uint64_t>(resource + 1592) + (uint64_t)plan.sub_mesh * 0x270;
        if (!(m.rd<uint8_t>(plan.record + 88) & 1)) return EntryWay::NoRecorded;
        if (!((m.rd<uint8_t>(block + kBlockMode) >> 5) & 1)) return EntryWay::NoListAllowed;
        if (m.inline_write()) return EntryWay::InlineWrite;
    }
    plan.command_buffer = m.rd<uint64_t>(m.rd<uint64_t>(block + kBlockContext) + 216);
    return EntryWay::Native;
}

namespace {
// The byte the report marks used: the query's flag array at the report's slot, wrapped to the ring's size
GuestAddr report_byte(const Mem& m, const KeyLoopEntry& p) {
    const uint32_t per = (uint32_t)m.rd<uint16_t>(p.query + 12) * m.rd<uint8_t>(p.query + 15);
    const uint32_t used = per + p.base + p.index, size = m.rd<uint32_t>(p.query + 24);
    return m.rd<uint64_t>(p.query + 32) + (int64_t)(int32_t)(used < size ? used : 0);
}
}   // namespace

// The cluster path's draw: the entry's list holds records of three u16 (the first index range, how many ranges, the
// descriptor), ended by a record with no ranges. Each record is one indexed draw from the descriptor's index buffer:
// the ranges are adjacent, so one draw from the first range's offset covers them to the end of the last. The block's
// triangle counter takes a third of each draw's index count.
template <class Address>
void draw_clusters(const Mem& m, const KeyLoopEntry& p, GuestAddr block, gfx::CommandSink& sink, Address&& address) {
    using gfx::command;
    using gfx::Proc;
    const GuestAddr descriptors = m.rd<uint64_t>(m.rd<uint64_t>(p.resource + 8) + 24);
    uint32_t triangles = 0;
    GuestAddr record = p.cluster_list;
    for (uint32_t ranges = m.rd<uint16_t>(record + 2); ranges != 0; ranges = m.rd<uint16_t>(record + 2)) {
        const GuestAddr desc = descriptors + (uint64_t)m.rd<uint16_t>(record + 4) * sizeof(guest::SubmeshDescriptor);
        const GuestAddr first = m.rd<uint64_t>(desc) + (uint64_t)m.rd<uint16_t>(record) * 8;
        const GuestAddr last = first + ((uint64_t)ranges << 3) - 8;
        const uint32_t first_offset = m.rd<uint32_t>(first);
        const uint32_t shift = m.rd<uint32_t>(desc + offsetof(guest::SubmeshDescriptor, index_type));
        const uint64_t span = (uint64_t)m.rd<uint32_t>(last) - (uint64_t)first_offset;
        const uint32_t count = m.rd<uint32_t>(last + 4) + (uint32_t)(span >> (shift & 63));
        const uint32_t primitive = m.rd<uint32_t>(desc + offsetof(guest::SubmeshDescriptor, primitive));
        const uint64_t base = address(m.rd<uint64_t>(m.rd<uint64_t>(desc + offsetof(guest::SubmeshDescriptor, index_holder)) + 8));
        sink.emit(command(Proc::CommandBufferDrawElementsInstanced, p.command_buffer,
                          m.rd<uint32_t>(kPrimitiveTable + 4ull * primitive), m.rd<uint32_t>(kIndexTypeTable + 4ull * shift),
                          count, base + first_offset, m.rd<uint32_t>(desc + offsetof(guest::SubmeshDescriptor, base_vertex)), 1, 1));
        const int64_t product = (int64_t)(int32_t)count * 0x55555556ll;
        triangles += (uint32_t)(product >> 32) + (uint32_t)((uint64_t)product >> 63);
        record += 6;
    }
    m.wr<uint32_t>(block + kBlockTriangles, m.rd<uint32_t>(block + kBlockTriangles) + triangles);
}

// The render-enable function (guest 0x80078b10, inlined in the draw function): the entry's render enable is kept in the
// block, a conditional render in force is turned off (SetRenderEnable) and the block's derived fields are rewritten from
// its flag bytes. It records nothing else.
template <class Mark>
void apply_enable(const Mem& m, const KeyLoopEntry& p, GuestAddr block, gfx::CommandSink& sink, Mark&& mark) {
    m.wr<uint8_t>(block + kBlockEnableApplied, (uint8_t)((p.bits >> 4) & 1));
    const uint64_t query = m.rd<uint64_t>(block + kBlockQuery);
    if (!(query == 0 && m.rd<uint32_t>(block + kBlockQueryIndex) == 0)) {
        if (query != 0) {
            mark();
            sink.emit(gfx::command(gfx::Proc::CommandBufferSetRenderEnable, p.command_buffer, 1));
        }
        m.wr<uint64_t>(block + kBlockQuery, 0);
        m.wr<uint32_t>(block + kBlockQueryIndex, 0xffffffffu);
    }
    const uint32_t first = m.rd<uint8_t>(block + 89), mode = m.rd<uint32_t>(block + kBlockMode), faces = m.rd<uint8_t>(block + 349);
    const uint32_t both = ((mode & 0x200) ? first | 3 : first) | m.rd<uint8_t>(block + 58);
    const uint32_t low = both & 0xff, depth = both & 4;
    const uint32_t set = depth != 0 ? 1u : 0u;
    if (((faces ^ (depth >> 2)) & 1) || ((set ^ ((faces & 2) >> 1)) & 1) || (set - ((faces & 4) >> 2)) != 0)
        m.wr<uint8_t>(block + 349, (uint8_t)((faces & 0xfe) | (depth >> 2)));
    uint32_t cull = low & 3;
    if (cull == 0)
        cull = 3;
    else if (cull == 1)
        cull = (low & 8) ? 1 : 2;
    else if (cull == 3)
        cull = 0;
    else
        cull = (low & 8) ? 2 : 1;
    if (cull != m.rd<uint8_t>(block + 341)) m.wr<uint8_t>(block + 341, (uint8_t)cull);
    const uint32_t polygon = (low >> 4) & 3;
    const uint32_t fill = polygon == 2 ? 0 : (polygon == 1 ? 1u : 2u);
    if (!(fill == m.rd<uint8_t>(block + 347) && fill == m.rd<uint8_t>(block + 348))) {
        m.wr<uint8_t>(block + 347, (uint8_t)fill);
        m.wr<uint8_t>(block + 348, (uint8_t)fill);
    }
    m.wr<uint64_t>(block + 208, 0);
    m.wr<uint64_t>(block + 216, 0);
    m.wr<uint16_t>(block + 178, 0);
    m.wr<uint8_t>(block + 88, 8);
    m.wr<uint8_t>(block + kBlockKeyApplied, 0xff);
    m.wr<uint8_t>(block + 96, 0xff);
    for (uint64_t at = 120; at < 152; at += 8) m.wr<uint64_t>(block + at, ~0ull);
    m.wr<uint32_t>(block + 152, 0xffffffffu);
    m.wr<uint32_t>(block + kBlockMode, mode & 0xffff4fffu);
}

// The render state: the sub-key (with bit 7 when the block's mask meets the entry, and the block's mode bit 19 for the
// entry's bit 10) against the one applied last; when it differs, the render-state function's work (hl/gfx/RenderState.h)
// with its five state objects where the draw function's frame has them.
void apply_state(GuestRuntime& runtime, const Mem& m, const KeyLoopCall& call, const KeyLoopEntry& p, gfx::CommandSink& sink) {
    const GuestAddr block = call.block;
    uint32_t key = p.bits & 0xf;
    if (m.rd<uint32_t>(block + kBlockMask) & p.kind) {
        if ((p.bits >> 10) & 1)
            key |= (m.rd<uint32_t>(block + kBlockMode) >> 13) & 0x40;
        else
            key |= 0xffffff80u;
    }
    if (m.rd<uint8_t>(block + kBlockKeyApplied) == (uint8_t)key) return;
    const StateBridge bridge(runtime);
    const uint64_t frame = call.sp - kKeyLoopFrame;
    gfx::StateInputs in;
    gfx::StateHandles at;
    bridge.read(block, key, StateBridge::Objects{frame + 168, frame + 144, frame + 148, frame + 152, frame + 140}, in, at);
    const gfx::StateOutputs out = gfx::RenderState::decide(in, bridge.offsets(block));
    bridge.write(block, out);   // (the block first: the blend color call reads it from there)
    gfx::RenderState::emit(in, out, at, sink);
}

void KeyLoopBridge::snapshot_prepare(GuestAddr block, GuestAddr command_buffer, uint8_t* bytes) const {
    std::memcpy(bytes, runtime_.ptr(block), 352);
    bytes[352] = command_buffer ? *(const uint8_t*)runtime_.ptr(command_buffer + 0x10) : 0;
}

void KeyLoopBridge::restore_prepare(GuestAddr block, GuestAddr command_buffer, const uint8_t* bytes) const {
    std::memcpy(runtime_.ptr(block), bytes, 352);
    runtime_.written(block, 352);
    if (command_buffer) {
        *(uint8_t*)runtime_.ptr(command_buffer + 0x10) = bytes[352];
        runtime_.written(command_buffer + 0x10, 1);
    }
}

void KeyLoopBridge::snapshot(const KeyLoopCall& call, const KeyLoopEntry& p, uint8_t* bytes) const {
    const Mem m{runtime_};
    snapshot_prepare(call.block, p.command_buffer, bytes);
    uint32_t stamp = 0;
    uint8_t used = 0;
    if (p.reset) stamp = m.rd<uint32_t>(p.query + 40), used = m.rd<uint8_t>(report_byte(m, p));
    std::memcpy(bytes + 353, &stamp, 4);
    bytes[357] = used;
}

void KeyLoopBridge::restore(const KeyLoopCall& call, const KeyLoopEntry& p, const uint8_t* bytes) const {
    const Mem m{runtime_};
    restore_prepare(call.block, p.command_buffer, bytes);
    if (!p.reset) return;
    uint32_t stamp;
    std::memcpy(&stamp, bytes + 353, 4);
    m.wr<uint32_t>(p.query + 40, stamp);
    m.wr<uint8_t>(report_byte(m, p), bytes[357]);
}

void KeyLoopBridge::run(const KeyLoopCall& call, const KeyLoopEntry& p, const Prepare& prepare, gfx::CommandSink& sink,
                        const gfx::NvnEntryPoints& nvn) const {
    using gfx::command;
    using gfx::Proc;
    const Mem m{runtime_};
    const GuestAddr block = call.block, cb = p.command_buffer;
    // (the byte the game's NVN command buffer object keeps to say commands were recorded: set before each call)
    auto mark = [&] { m.wr<uint8_t>(cb + 0x10, 1); };
    // (a query's buffer address, asked of the NVN layer: a query changes nothing; the stream carries it for the check)
    auto address = [&](GuestAddr buffer) {
        const gfx::Command c = command(Proc::BufferGetAddress, buffer);
        const uint64_t a = nvn.ask(c);
        sink.emit(c);
        return a;
    };
    auto slot = [&](uint32_t index) { return (uint64_t)index << 5; };
    const uint32_t per = p.query ? (uint32_t)m.rd<uint16_t>(p.query + 12) * m.rd<uint8_t>(p.query + 15) : 0;

    if (p.enable_changes) apply_enable(m, p, block, sink, mark);
    apply_state(runtime_, m, call, p, sink);

    if (p.reset) {
        mark();
        sink.emit(command(Proc::CommandBufferResetCounter, cb, 1));
        m.wr<uint32_t>(p.query + 40, m.rd<uint32_t>(block + kBlockFrame));
    }
    if (p.no_query) {
        // (no query to render by: the enable goes back on, and the block remembers there was none)
        if (p.was_conditional) {
            mark();
            sink.emit(command(Proc::CommandBufferSetRenderEnable, cb, 1));
        }
        m.wr<uint64_t>(block + kBlockQuery, 0);
        m.wr<uint32_t>(block + kBlockQueryIndex, 0xffffffffu);
    }
    if (p.conditional) {
        if (p.was_conditional) {
            mark();
            sink.emit(command(Proc::CommandBufferSetRenderEnable, cb, 1));
        }
        const uint64_t a = address(p.query + 80);
        mark();
        sink.emit(command(Proc::CommandBufferSetRenderEnableConditional, cb, 1, a + slot(p.index + per)));
        m.wr<uint64_t>(block + kBlockQuery, p.query);
        m.wr<uint32_t>(block + kBlockQueryIndex, p.index);
    }
    if (p.in_range) {
        const uint64_t prepared = prepare(block, p.drawable);
        if ((prepared & 1) && p.cluster_list) {
            draw_clusters(m, p, block, sink, address);
        } else if (prepared & 1) {
            mark();
            sink.emit(command(Proc::CommandBufferCallCommands, cb, 1, p.record + 80));
            m.wr<uint32_t>(block + kBlockTriangles, m.rd<uint32_t>(block + kBlockTriangles) + m.rd<uint32_t>(p.record + 616));
        }
    }
    if (p.reset) {
        // (the report's slot is recorded as used, wrapped to the ring's size; the address is not wrapped)
        const uint32_t used = per + p.base + p.index;
        const GuestAddr byte = report_byte(m, p);
        m.wr<uint8_t>(byte, m.rd<uint8_t>(byte) | 1);
        const uint64_t a = address(p.query + 80);
        mark();
        sink.emit(command(Proc::CommandBufferReportCounter, cb, 1, a + slot(used)));
    }
}

}   // namespace hl::bridge
