"""The capture's pool list keys the pools' starts with PoolStartHash (gpu/vk/vk_memory.cpp, refresh_pool_ranges_locked).

The starts are 64 KB aligned and std::hash<uint64_t> is the identity. With 8192 pools, seen.reserve(8192) asks libc++ for a
power-of-two bucket count, which it keeps and masks with: every start in bucket 0, each find and insert a walk of the whole
chain (~20 ms a refresh in the Market on Windows). libstdc++ rounds to a prime, so a map alone shows nothing on Linux: the
fixture checks the hash's low bits as libc++'s mask takes them, for starts 64 KB and 2 MB apart, and that both maps use it.
python -I -B tests/test_pool_start_hash.py [--cxx g++]
"""
import argparse
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FIXTURE = r'''
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <unordered_map>
#include <vector>
#define CHECK(x) do { if (!(x)) { std::fprintf(stderr, "FAIL:%d %s\n", __LINE__, #x); std::exit(1); } } while (0)
/* ACTUAL */
template <class H> static size_t worst_bucket(uint64_t base, uint64_t step, size_t n, size_t buckets) {
    std::vector<size_t> load(buckets);
    size_t worst = 0;
    for (size_t i = 0; i < n; i++) {
        const size_t b = H{}((base + i * step)) & (buckets - 1);   // (libc++ with a power-of-two bucket count)
        if (++load[b] > worst) worst = load[b];
    }
    return worst;
}
struct Identity { size_t operator()(uint64_t k) const { return (size_t)k; } };
int main() {
    for (const size_t n : {1024u, 4096u, 8192u}) {
        for (const uint64_t step : {0x10000ull, 0x200000ull}) {
            // (as the bug was: every start in one bucket)
            CHECK(worst_bucket<Identity>(0x8000000000ull >> 8, step, n, n) == n);
            CHECK(worst_bucket<PoolStartHash>(0x8000000000ull >> 8, step, n, n) <= 12);
            CHECK(worst_bucket<PoolStartHash>(0x1234560000ull, step, n, n) <= 12);
        }
    }
    std::unordered_map<uint64_t, uint64_t, PoolStartHash> m;   // (the map as the refresh uses it)
    m.reserve(8192);
    for (uint64_t i = 0; i < 8192; i++) m[0x100000000ull + i * 0x10000] = i;
    size_t worst = 0;
    for (size_t b = 0; b < m.bucket_count(); b++) worst = m.bucket_size(b) > worst ? m.bucket_size(b) : worst;
    CHECK(m.size() == 8192 && worst <= 12);
    std::puts("PASS: the pools' starts spread over the buckets, a power-of-two count included");
    return 0;
}
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cxx", default="g++")
    a = p.parse_args()
    source = (ROOT / "gpu" / "vk" / "vk_memory.cpp").read_text(encoding="utf-8")
    m = re.search(r"^struct PoolStartHash \{.*?^\};\n", source, re.S | re.M)
    if not m:
        raise SystemExit("vk_memory.cpp: no struct PoolStartHash")
    for needle in ("std::unordered_map<uint64_t, uint64_t, PoolStartHash> pool_first_seen;",
                   "    std::unordered_map<uint64_t, uint64_t, PoolStartHash> seen;"):
        if needle not in source:
            raise SystemExit("vk_memory.cpp: missing %r (a pool map keyed with std::hash again)" % needle)
    with tempfile.TemporaryDirectory(prefix="pool-start-hash-") as tmp:
        cpp = Path(tmp) / "fixture.cpp"
        exe = Path(tmp) / "fixture"
        cpp.write_text(FIXTURE.replace("/* ACTUAL */", m.group(0)), encoding="utf-8")
        subprocess.run([a.cxx, "-std=c++20", "-O1", "-Wall", "-Wextra", "-Werror", str(cpp), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == "__main__":
    main()
