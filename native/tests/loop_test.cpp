// Hookshot native engine: the key-0xa0 draw function's entries (hl/bridge/LoopBridge.h) on a model of guest memory.
#include <cstdio>
#include <cstring>
#include <vector>

#include "hl/bridge/LoopBridge.h"
#include "hl/gfx/PassCheck.h"

using namespace hl;

namespace {
int failures = 0;
#define CHECK(x)                                                                \
    do {                                                                        \
        if (!(x)) {                                                             \
            std::printf("loop_test: FAILED line %d: %s\n", __LINE__, #x);       \
            failures++;                                                         \
        }                                                                       \
    } while (0)

// guest memory: a sparse model, the addresses used here at their real places
struct Model final : bridge::GuestRuntime {
    std::vector<uint8_t> low = std::vector<uint8_t>(0x20000), high = std::vector<uint8_t>(0x1000);
    void* ptr(bridge::GuestAddr a) const override {
        if (a >= 0x84ca2000 && a < 0x84cb6000 + 0x1000) return const_cast<uint8_t*>(&high[0]) + (a - 0x84ca2000) % 0x1000 + 0;
        return const_cast<uint8_t*>(&low[0]) + a % low.size();
    }
    bridge::GuestThread current() const override { return nullptr; }
    uint64_t call(bridge::GuestThread, bridge::GuestAddr, uint64_t, uint64_t) override { return 0; }
    uint64_t call_with(bridge::GuestThread, bridge::GuestAddr, const uint64_t*, unsigned, const void*, unsigned) override { return 0; }
    void log(const char*) override {}
};
}   // namespace

int main() {
    // (the three GOT slots live above 0x84ca2000: the model folds them into one page, so every slot reads as the same
    // value; with all three equal the "usual method" tests hold when the vtable slots read the same value too)
    Model m;
    bridge::KeyLoopBridge loop(m);
    bridge::KeyLoopCall call;
    call.block = 0x1000, call.mask = 1;
    bridge::KeyLoopEntry plan;
    auto w32 = [&](uint64_t a, uint32_t v) { std::memcpy(m.ptr(a), &v, 4); };
    // a masked entry does nothing
    w32(0x2000 + 8, 2);
    CHECK(loop.classify(call, 0x2000, plan) == bridge::EntryWay::Masked);
    // a render enable or state change is answered natively, but not when the material has a state callback (guest
    // code): this block has no material
    w32(0x2000 + 8, 1);
    uint16_t h = 1u << 4;
    std::memcpy(m.ptr(0x2000 + 14), &h, 2);
    CHECK(loop.classify(call, 0x2000, plan) == bridge::EntryWay::StateChange);
    h = 3;
    std::memcpy(m.ptr(0x2000 + 14), &h, 2);
    CHECK(loop.classify(call, 0x2000, plan) == bridge::EntryWay::StateChange);
    CHECK(std::strcmp(bridge::entry_way_name(bridge::EntryWay::Native), "native") == 0);
    CHECK(std::strcmp(bridge::entry_way_name(bridge::EntryWay::NoListAllowed), "nolist") == 0);
    // the snapshot and restore of the bytes an entry may write round-trip
    uint8_t before[bridge::KeyLoopBridge::kPrepareSize], after[bridge::KeyLoopBridge::kPrepareSize];
    loop.snapshot_prepare(0x1000, 0, before);
    w32(0x1000 + 80, 77);
    loop.restore_prepare(0x1000, 0, before);
    loop.snapshot_prepare(0x1000, 0, after);
    CHECK(std::memcmp(before, after, sizeof before) == 0);
    if (!failures) std::printf("loop_test: ok\n");
    return failures ? 1 : 0;
}
