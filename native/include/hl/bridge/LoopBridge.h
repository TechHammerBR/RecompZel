// Hookshot native engine: the recording job's key-0xa0 draw function (guest 0x8008d640), where it meets its native
// parts (docs/native-engine/gfx-record-job.md, section 13).
//
// The job's item body picks a draw function by the key it computes from the draw's flag bits and calls it through a
// table with (the item's list of draw entries, their count, the render-state block, the key's first word, the item's
// flags). Key 0xa0's function is the job's own draw loop specialized for one key: per draw entry (a drawable and one
// of its sub-meshes) it changes the render enable and the render state when the entry's differ from the block's, runs
// the drawable's occlusion query around the draw, calls the shared preparation and submits the sub-mesh.
//
// KeyLoopBridge reads one entry the way the function does and says whether the native version answers it (the plain
// path: the same render enable and state as the block's, a pre-recorded command list to call, the paths the lifted code
// takes in the scenes) or leaves it to the translation, which the OS layer then runs on that one entry (the function
// is a loop over its list and keeps nothing between entries but the block and the command buffer). run() is the native
// entry: the same writes in place and the same NVN calls, in the function's order.
#pragma once

#include <cstddef>
#include <cstdint>
#include <functional>

#include "hl/bridge/JobBridge.h"
#include "hl/gfx/Commands.h"
#include "hl/gfx/Nvn.h"

namespace hl::bridge {

inline constexpr GuestAddr kKeyLoopFn = 0x8008d640;
/// The call of the shared preparation the function makes, and the frame it sets up before it.
inline constexpr GuestAddr kKeyLoopPrepareReturn = 0x8008d8ec;
inline constexpr uint64_t kKeyLoopFrame = 432;

/// One call of the function: x0 the list (draw entries' pointers), w1 their count, x2 the block, x3 the key's first word
/// (an entry whose kind mask +8 does not meet it is skipped), w5 the item's flags; `sp` the stack pointer at the entry.
struct KeyLoopCall {
    GuestAddr list = 0;
    uint32_t count = 0;
    GuestAddr block = 0;
    uint64_t mask = 0;
    uint32_t flags = 0;
    uint64_t sp = 0;
};

/// Why an entry is or is not answered natively: the first test of the function's order it fails.
enum class EntryWay : uint8_t {
    Native,         ///< the plain path
    Masked,         ///< the entry's kind mask does not meet the key: the function does nothing for it (native)
    EnableChange,   ///< the render enable changes and the conditional render's switch is set while the inline-write switch is
    StateChange,    ///< the render state may change and the material has a state callback (guest code)
    ModelClass,     ///< the model's occlusion method is not the game's usual one (a virtual call)
    InlineWrite,    ///< the inline-write switch is set
    Method,         ///< the drawable's submission method is not the game's (a call)
    Geometry,       ///< the geometry processing mode changes
    FlagsMask,      ///< the drawable's flags meet the item's flag bit 3
    FlagsBit5,      ///< the drawable's flag bit 5
    Indirect,       ///< the indirect draw (kind bit 4)
    ClusterOther,   ///< the cluster paths: the drawable's cluster entry is not the plain list of index ranges
    ClusterCull,    ///< ... the culling loop (kind bit 7)
    ClusterPlain,   ///< ... the other cluster path
    Instances,      ///< more than one instance
    NoRecorded,     ///< the sub-mesh has no pre-recorded list
    NoListAllowed,  ///< the block does not allow pre-recorded lists
    Count
};
const char* entry_way_name(EntryWay way);

/// What the function reads of one entry before it writes anything, in place.
struct KeyLoopEntry {
    GuestAddr entry = 0, drawable = 0, model = 0, resource = 0, query = 0, record = 0, command_buffer = 0;
    uint16_t bits = 0;         ///< the entry's flag bits (+14): the state sub-key, the render enable, the sub-mesh
    uint32_t kind = 0;         ///< the entry's kind mask (+8)
    bool enable_changes = false;   ///< the render enable differs from the block's: the render-enable function runs
    GuestAddr method = 0;      ///< the drawable's submission method (the way Method: which one)
    GuestAddr cluster_list = 0;   ///< the cluster path's list of (range, count, descriptor) records (0: not that path)
    uint32_t pass = 0;       ///< the block's pass slot
    uint32_t index = 0;      ///< the query slot the entry uses
    uint32_t base = 0;       ///< the pass's query base
    uint32_t sub_mesh = 0;
    bool in_range = false;   ///< the sub-mesh exists: it is prepared and submitted
    bool reset = false;      ///< the query is reset first, and reported after the draw
    bool conditional = false;   ///< the render enable is set from the query
    bool no_query = false;      ///< conditional rendering with no query object: the enable is turned back on, none set
    bool was_conditional = false;   ///< ... after one already set (turned back on first)
};

class KeyLoopBridge {
public:
    explicit KeyLoopBridge(GuestRuntime& runtime) : runtime_(runtime) {}

    /// Reads one entry; fills `plan` when the answer is Native.
    EntryWay classify(const KeyLoopCall& call, GuestAddr entry, KeyLoopEntry& plan) const;

    /// The shared preparation, called on the function's own context below its frame (the result's bit 0: go on).
    using Prepare = std::function<uint64_t(GuestAddr block, GuestAddr drawable)>;
    /// What an entry may write: the block's 352 bytes, the command buffer object's mark byte, the query object's frame
    /// stamp and the byte its report marks used (the last two zero without a query).
    static constexpr size_t kSnapshotSize = 352 + 1 + 4 + 1;
    void snapshot(const KeyLoopCall& call, const KeyLoopEntry& plan, uint8_t* bytes) const;
    void restore(const KeyLoopCall& call, const KeyLoopEntry& plan, const uint8_t* bytes) const;
    /// The block and mark byte only (what the shared preparation may write), now / put back.
    static constexpr size_t kPrepareSize = 352 + 1;
    void snapshot_prepare(GuestAddr block, GuestAddr command_buffer, uint8_t* bytes) const;
    void restore_prepare(GuestAddr block, GuestAddr command_buffer, const uint8_t* bytes) const;

    /// The entry's writes and NVN calls (into `sink`; the queries asked through `nvn`).
    void run(const KeyLoopCall& call, const KeyLoopEntry& plan, const Prepare& prepare, gfx::CommandSink& sink,
             const gfx::NvnEntryPoints& nvn) const;

private:
    GuestRuntime& runtime_;
};

}   // namespace hl::bridge
