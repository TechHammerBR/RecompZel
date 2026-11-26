// The constant propagation pass's fold of an instruction of immediates that has flag pseudo-operations (RX_VK_FOLD_PSEUDO).
// Builds real IR (shader_recompiler/frontend/ir) and runs ConstantPropagationPass over it: argv[1] is "on" or "off".
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>

#include "shader_recompiler/environment.h"
#include "shader_recompiler/frontend/ir/basic_block.h"
#include "shader_recompiler/frontend/ir/ir_emitter.h"
#include "shader_recompiler/frontend/ir/program.h"
#include "shader_recompiler/ir_opt/passes.h"
#include "shader_recompiler/ir_opt/pseudo_fold.h"

using namespace Shader;

static int failures = 0;
#define CHECK(x) do { if (!(x)) { std::printf("FAIL line %d: %s\n", __LINE__, #x); ++failures; } } while (0)

namespace {
class Env final : public Environment {
public:
    u64 ReadInstruction(u32) override { return 0; }
    u32 ReadCbufValue(u32, u32) override { return 0; }
    TextureType ReadTextureType(u32) override { return {}; }
    TexturePixelFormat ReadTexturePixelFormat(u32) override { return {}; }
    bool IsTexturePixelFormatInteger(u32) override { return false; }
    u32 ReadViewportTransformState() override { return 0; }
    u32 TextureBoundBuffer() const override { return 0; }
    u32 LocalMemorySize() const override { return 0; }
    u32 SharedMemorySize() const override { return 0; }
    std::array<u32, 3> WorkgroupSize() const override { return {1, 1, 1}; }
    bool HasHLEMacroState() const override { return false; }
    std::optional<ReplaceConstant> GetReplaceConstBuffer(u32, u32) override { return std::nullopt; }
    void Dump(u64, u64) override {}
};

bool IsImm(const IR::Value& v, bool expect) {
    const IR::Value r{v.Resolve()};
    return r.IsImmediate() && r.U1() == expect;
}
bool IsImmU32(const IR::Value& v, u32 expect) {
    const IR::Value r{v.Resolve()};
    return r.IsImmediate() && r.U32() == expect;
}
} // namespace

int main(int argc, char** argv) {
    const bool on{argc > 1 && !std::strcmp(argv[1], "on")};
    CHECK(Optimization::FoldPseudoEnabled(on ? "1" : "0") == on);
    CHECK(!Optimization::FoldPseudoEnabled(nullptr));
    CHECK(!Optimization::FoldPseudoEnabled(""));
    CHECK(!Optimization::FoldPseudoEnabled("abc"));
    CHECK(Optimization::ZeroFlagOf(0) && !Optimization::ZeroFlagOf(1));
    CHECK(Optimization::SignFlagOf(0x80000000u) && !Optimization::SignFlagOf(0x7FFFFFFFu));
    // the switch is read once, at the first fold
#ifdef _WIN32
    _putenv_s("RX_VK_FOLD_PSEUDO", on ? "1" : "0");
#else
    setenv("RX_VK_FOLD_PSEUDO", on ? "1" : "0", 1);
#endif

    ObjectPool<IR::Inst> inst_pool;
    ObjectPool<IR::Block> block_pool;
    IR::Program program{};
    IR::Block* const block{block_pool.Create(inst_pool)};
    program.blocks.push_back(block);
    program.post_order_blocks.push_back(block);
    IR::IREmitter ir{*block};

    const IR::U32 r1{ir.GetReg(IR::Reg::R1)};
    const IR::U32 r2{ir.GetReg(IR::Reg::R2)};

    // 1. R2P's shape: BitFieldExtract(0b0101, 0, 1) -> 1, zero flag false: the Select takes its false value
    const IR::U32 e1{ir.BitFieldExtract(ir.Imm32(5), ir.Imm32(0), ir.Imm32(1), false)};
    const IR::U1 z1{ir.GetZeroFromOp(e1)};
    const IR::Value sel1{ir.Select(z1, r1, r2)};
    const IR::U1 not1{ir.LogicalNot(z1)};
    // 2. extract of 0 -> zero flag true
    const IR::U32 e2{ir.BitFieldExtract(ir.Imm32(5), ir.Imm32(1), ir.Imm32(1), false)};
    const IR::U1 z2{ir.GetZeroFromOp(e2)};
    const IR::Value sel2{ir.Select(z2, r1, r2)};
    const IR::U1 not2{ir.LogicalNot(z2)};
    // 3. a signed extract of the top bit: 0xFFFFFFFF, sign flag true, zero flag false
    const IR::U32 e3{ir.BitFieldExtract(ir.Imm32(0x80000000u), ir.Imm32(31), ir.Imm32(1), true)};
    const IR::U1 z3{ir.GetZeroFromOp(e3)};
    const IR::U1 s3{ir.GetSignFromOp(e3)};
    // 4. an unsigned extract of the top bit: 1, sign flag false (as the back end's OpSLessThan(1, 0))
    const IR::U32 e4{ir.BitFieldExtract(ir.Imm32(0x80000000u), ir.Imm32(31), ir.Imm32(1), false)};
    const IR::U1 s4{ir.GetSignFromOp(e4)};
    // 5. BitwiseAnd(0x80000000, 0xF0000000) -> zero false, sign true
    const IR::U32 e5{ir.BitwiseAnd(ir.Imm32(0x80000000u), ir.Imm32(0xF0000000u))};
    const IR::U1 z5{ir.GetZeroFromOp(e5)};
    const IR::U1 s5{ir.GetSignFromOp(e5)};
    // 6. BitwiseAnd(0xF0, 0x0F) -> 0, zero true
    const IR::U32 e6{ir.BitwiseAnd(ir.Imm32(0xF0), ir.Imm32(0x0F))};
    const IR::U1 z6{ir.GetZeroFromOp(e6)};
    // 7. not constant: the extract of a register keeps its flag and itself
    const IR::U32 e7{ir.BitFieldExtract(r1, ir.Imm32(0), ir.Imm32(1), false)};
    const IR::U1 z7{ir.GetZeroFromOp(e7)};
    // 8. no pseudo-operation: folds with or without the switch
    const IR::U32 e8{ir.BitFieldExtract(ir.Imm32(6), ir.Imm32(1), ir.Imm32(2), false)};
    // consumers of the results themselves
    const IR::U32 x1{ir.BitwiseXor(e1, ir.Imm32(0x10))};
    const IR::U32 x3{ir.BitwiseXor(e3, ir.Imm32(0xFF))};

    Env env;
    Optimization::ConstantPropagationPass(env, program);

    CHECK(IsImmU32(e8, 3));   // (6 >> 1) & 3, no flag: folded either way
    CHECK(!e7.Resolve().IsImmediate());
    CHECK(!z7.Resolve().IsImmediate());
    if (on) {
        CHECK(IsImm(z1, false));
        CHECK(IsImm(not1, true));
        CHECK(sel1.Resolve() == r2.Resolve());
        CHECK(IsImm(z2, true));
        CHECK(IsImm(not2, false));
        CHECK(sel2.Resolve() == r1.Resolve());
        CHECK(IsImmU32(e3, 0xFFFFFFFFu));
        CHECK(IsImm(z3, false));
        CHECK(IsImm(s3, true));
        CHECK(IsImmU32(e4, 1));
        CHECK(IsImm(s4, false));
        CHECK(IsImm(z5, false));
        CHECK(IsImm(s5, true));
        CHECK(IsImmU32(e5, 0x80000000u));
        CHECK(IsImm(z6, true));
        CHECK(IsImmU32(e6, 0));
        CHECK(IsImmU32(e1, 1));
        CHECK(IsImmU32(x1, 0x11));
        CHECK(IsImmU32(x3, 0xFFFFFF00u));
    } else {
        // off: as before the switch, everything with a flag stays
        CHECK(!e1.Resolve().IsImmediate());
        CHECK(!z1.Resolve().IsImmediate());
        CHECK(!e3.Resolve().IsImmediate());
        CHECK(!e6.Resolve().IsImmediate());
        CHECK(!z6.Resolve().IsImmediate());
    }
    if (failures) {
        return 1;
    }
    std::printf("pseudo_fold %s: ok\n", on ? "on" : "off");
    return 0;
}
