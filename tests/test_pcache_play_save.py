"""The pipeline cache's save in play (gpu/vk/vk_draw.cpp pcache_play_save_gate, RX_VK_PCACHE_PLAY_SAVE).

A save in play fetches the whole cache (1.27 GB after a long session) into new file pages and writes it out; on a PC with
little free RAM those pages pushed the game's trimmed pages out, and the game stopped for seconds reading them back. The
gate lets a save in play run only with room for it (free physical memory at least twice the cache plus 4 GB) and not more
often than every 5 minutes (mode 1); mode 0 never saves in play, mode 2 always (the default, as before). Also checks that a
forced save (exit, prepare, Restart now) and the serial builds' save do not pass through the gate, that a put-off save
keeps its pipelines owed, and that the background save thread runs in Windows' background mode.

python -I -B tests/test_pcache_play_save.py [--cxx clang++]
"""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile

RUN_ALL_ARGS = ['--cxx', '{cxx}']
ROOT = Path(__file__).resolve().parents[1]


def block(text, marker):
    start = text.index(marker)
    end = text.index('{', start) + 1
    depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cxx', default='g++')
    parser.add_argument('--source', type=Path, default=ROOT / 'gpu/vk/vk_draw.cpp')
    args = parser.parse_args()
    text = args.source.read_text(encoding='utf-8')
    gate = block(text, 'int pcache_play_save_gate(')
    consts = '\n'.join(re.search(r'^constexpr \S+ %s = .*$' % n, text, re.M).group(0) for n in ('kPlaySaveSpareMB', 'kPlaySaveMinS'))
    save = block(text, 'void pipeline_cache_save(bool force)')
    asked = 'if (!force && !between && pcache_play_save_mode() < 2) {'
    if asked not in save or 'pcache_play_save_gate(' not in save:
        raise SystemExit('FAIL: the gate is not asked for saves in play only')
    mode = block(text, 'int pcache_play_save_mode()')
    if 'return e && *e ? atoi(e) : 2;' not in mode:
        raise SystemExit('FAIL: RX_VK_PCACHE_PLAY_SAVE is not 2 (every save, as before) by default')
    gated = save[save.index(asked):]
    gated = gated[:gated.index('const int64_t built = pcache_built_since_save.exchange(0);')]
    if 'exchange(' in gated:
        raise SystemExit('FAIL: a put-off save loses its owed pipelines')
    if 'THREAD_MODE_BACKGROUND_BEGIN' not in save:
        raise SystemExit('FAIL: the save in play does not run in background mode')
    fixture = '#include <cstdint>\n#include <cstdio>\n#include <cstdlib>\n' \
              '#define CHECK(ok) do { if (!(ok)) { std::fprintf(stderr, "failed line %d\\n", __LINE__); std::exit(1); } } while (0)\n' \
              + consts + '\n' + gate + r'''
int main() {
    const uint64_t MB = 1 << 20, GB = MB << 10;
    // the owner's session: 1.27 GB of cache, ~5 GB available: put off for room
    CHECK(pcache_play_save_gate(1, 5 * GB, 1300 * MB, 600) == 1);
    // room for it, the last save long ago or none yet: saved
    CHECK(pcache_play_save_gate(1, 8 * GB, 1300 * MB, 600) == 0);
    CHECK(pcache_play_save_gate(1, 8 * GB, 1300 * MB, -1) == 0);
    // room, but the last save in play 2 minutes ago: put off for the interval
    CHECK(pcache_play_save_gate(1, 8 * GB, 1300 * MB, 120) == 2);
    // the edge of the room rule: twice the cache plus 4 GB
    CHECK(pcache_play_save_gate(1, 2 * 1300 * MB + 4 * GB, 1300 * MB, -1) == 0);
    CHECK(pcache_play_save_gate(1, 2 * 1300 * MB + 4 * GB - 1, 1300 * MB, -1) == 1);
    // 0: never in play; 2: always, as before
    CHECK(pcache_play_save_gate(0, 64 * GB, 1 * MB, -1) == 3);
    CHECK(pcache_play_save_gate(2, 0, 1300 * MB, 1) == 0);
    std::puts("PASS: saves in play only with room and 5 minutes apart (0 never, 2 as before); forced saves ungated; "
              "owed pipelines kept; background mode");
}
'''
    with tempfile.TemporaryDirectory(prefix='pcache-play-') as tmp:
        cpp = Path(tmp) / 'fixture.cpp'
        exe = Path(tmp) / 'fixture.exe'
        cpp.write_text(fixture, encoding='utf-8')
        subprocess.run([args.cxx, '-std=c++20', '-Wall', '-Wextra', '-Werror', str(cpp), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    main()
