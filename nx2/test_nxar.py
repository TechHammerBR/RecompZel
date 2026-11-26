"""Game-free check of the .nx (NXFormat) reader: archives built here from the format's specification; requires zstandard.
python -I -B nx2/test_nxar.py
"""
import argparse
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
from pathlib import Path
import struct
import sys
import tempfile
import zstandard

RUN_ALL_MODULES = ["zstandard"]

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1])
a = p.parse_args()
sys.path.insert(0, str(a.source/'nx2'))   # (nxar.py imports nup.py from its own folder)
spec = importlib.util.spec_from_file_location('tested_nxar', a.source/'nx2/nxar.py')
nxar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nxar)
nup = nxar.nup

assert nxar.crc32c(b'123456789') == 0xe3069283, 'CRC-32C check value'

NONE = 0xffffffff
EMPTY = hashlib.sha256().digest()


def align(n, to):
    return (n + to - 1) & -to


def seal(blob, slot):
    """A header slot's CRC written again after its fields were changed"""
    at = slot * 4096
    struct.pack_into('<I', blob, at + 252, nxar.crc32c(bytes(blob[at:at + 252])))


def archive(snapshots, *, packed=(), chunk_log2=16):
    """snapshots: (type, version, has a program, tree), a tree a dict of name -> bytes or a tree. packed: the file names
    stored as zstd blocks. One application and one program, laid out as docs/SPEC.md of NXFormat 1.0.3 says"""
    dirs, files, refs, blocks, pool = [], [], [], [], bytearray()

    def add_file(name, data):
        first = len(refs)
        for at in range(0, len(data), 1 << chunk_log2):
            chunk = data[at:at + (1 << chunk_log2)]
            stored = zstandard.ZstdCompressor().compress(chunk) if name in packed else chunk
            refs.append(len(blocks))
            blocks.append((stored, len(chunk), 1 if name in packed else 0, chunk))
        files.append((len(data), first, len(refs) - first, hashlib.sha256(data).digest()))
        return len(files) - 1

    def add_dir(tree):
        index = len(dirs)
        dirs.append(None)
        entries = []
        for name in sorted(tree, key=str.encode):
            child = tree[name]
            entries.append((name.encode(), *((1, add_dir(child)) if isinstance(child, dict) else (2, add_file(name, child)))))
        dirs[index] = entries
        return index

    roots = [add_dir(tree) for _, _, _, tree in snapshots]

    blob = bytearray(8192)
    index, checks = bytearray(), bytearray()
    for stored, logical, codec, chunk in blocks:
        blob += bytes(align(len(blob), 16) - len(blob))
        index += struct.pack('<QIIBBHI', len(blob), len(stored), logical, codec, 0, 0, len(checks) // 4)
        for at in range(0, logical, 16384):
            checks += struct.pack('<I', nxar.crc32c(chunk[at:at + 16384]))
        blob += stored
    data_size = len(blob) - 8192 if blocks else 0

    n = len(snapshots)
    catalog = bytearray(128)
    catalog += struct.pack('<QBBH15I8s', 0x0400486024dec000, 2, 1, 0, 0, 1, 0, n, NONE, 0, NONE, 0, NONE, 0, 0, NONE, 0, 0, NONE, bytes(8))
    catalog += struct.pack('<QIBBH16sIIII16s', 0x0400486024dec000, 0, 0, 0, 0, bytes(16), 0, n, NONE, 0, bytes(16))
    for i, (kind, version, program, tree) in enumerate(snapshots):
        catalog += struct.pack('<IBBHIIQII16sII32s32s', 0 if program else NONE, kind, 0, 0, version, roots[i], 0, NONE, 0,
                               bytes(16), 0, 0, bytes([i + 1]) * 32, bytes(32))
    struct.pack_into('<4sHHQIIIIIIIIQQQQQQQQ', catalog, 0, b'NXCT', 1, 128, len(catalog), 0, 1, 1, n, 0, 0, 0, 0,
                     128, 208, 272, 0, 0, 0, len(catalog), 0)

    manifest = bytearray(96)
    dirs_at = len(manifest)
    at = 0
    for entries in dirs:
        manifest += struct.pack('<IIII', at, len(entries), 0, 0)
        at += len(entries)
    files_at = len(manifest) if files else 0
    for size, first, count, digest in files:
        manifest += struct.pack('<QIIBBH32s12s', size, first, count, chunk_log2, 0, 0, digest, bytes(12))
    entries_at = len(manifest)
    names = []
    for entries in dirs:
        for name, kind, target in entries:
            names.append((len(manifest), len(pool), len(name), target, kind))
            manifest += bytes(24)
            pool += name
    refs_at = len(manifest) if refs else 0
    manifest += b''.join(struct.pack('<I', r) for r in refs)
    manifest += bytes(align(len(manifest), 8) - len(manifest))
    pool_at = len(manifest)
    manifest += pool
    for where, name_at, name_len, target, kind in names:
        struct.pack_into('<QIIBBHI', manifest, where, pool_at + name_at, name_len, target, kind, 0, 0, 0)
    struct.pack_into('<4sHHQIIIIQQQQQQ16s', manifest, 0, b'NXMF', 1, 96, len(manifest), len(dirs), len(files), len(names),
                     len(refs), dirs_at, files_at, entries_at, refs_at, pool_at, len(pool), bytes(16))

    def tail(part):
        blob.extend(bytes(align(len(blob), 16) - len(blob)))
        at = len(blob)
        blob.extend(part)
        return at

    catalog_at, manifest_at = tail(catalog), tail(manifest)
    index_at = tail(index) if blocks else 0
    checks_at = tail(checks) if blocks else 0
    header = struct.pack('<4sHHIHH13Q32s32s32sQI24s', b'NXAR', 0, 2, 256, 1, 0, len(blob), catalog_at, len(catalog), 0, 0,
                         8192 if blocks else 0, data_size, manifest_at, len(manifest), index_at, len(blocks), checks_at,
                         len(checks), hashlib.sha256(catalog).digest(), hashlib.sha256(manifest).digest(),
                         hashlib.sha256(index + checks).digest(), 0, 16384, bytes(24))
    for slot in (0, 1):
        blob[slot * 4096:slot * 4096 + 252] = header
        seal(blob, slot)
    return blob


MAIN = b'NSO0' + bytes(range(256)) * 3
BIG = bytes((i * 7 + i // 251) & 255 for i in range(65536 * 2 + 17))   # (three blocks at 64 KiB)
GAME = [
    (0, 65536, True, {'exefs': {'main': b'NSO0 base', 'main.npdm': b'META'},
                      'romfs': {'base_only.bin': b'gone in the update', 'big.bin': BIG}}),
    (1, 131072, True, {'exefs': {'main': MAIN, 'main.npdm': b'META'},
                       'romfs': {'big.bin': BIG, 'empty.bin': b'', 'Model': {'a.bfres.zs': b'\x28\xb5\x2f\xfd' + b'model' * 9}}}),
    (2, 999999, False, {'romfs': {'dlc.bin': b'add-on content'}}),   # (an add-on, no program: never the game)
]


def refused(blob, path, extract=None):
    """The message an archive is refused with, at opening or at extraction"""
    path.write_bytes(blob)
    try:
        nx = nxar.Nx(str(path))
        with nx.f:
            if extract:
                with redirect_stdout(io.StringIO()):
                    nxar.extract(nx, None, str(extract))
    except SystemExit as error:
        return str(error.code)
    raise AssertionError('accepted an archive that must be refused')


with tempfile.TemporaryDirectory(prefix='nxar-') as temporary:
    root = Path(temporary)
    path = root / 'game.nx'
    good = archive(GAME, packed={'big.bin', 'main'})
    path.write_bytes(good)

    nx = nxar.Nx(str(path))
    with nx.f:
        assert [(t['version'], t['type']) for t in nx.titles] == [(65536, 0), (131072, 1)], nx.titles
        assert all(t['id'] == 0x0400486024dec000 for t in nx.titles)
        title = nup.pick_title(nx, None)
        assert title['version'] == 131072, 'the newest program snapshot is the game'
        assert sorted(rel for rel, _ in nx.walk(title['romfs'])) == ['Model/a.bfres.zs', 'big.bin', 'empty.bin']
        assert nx.read(next(r for rel, r in nx.walk(title['exefs']) if rel == 'main')) == MAIN
        out = root / 'out'
        with redirect_stdout(io.StringIO()):
            nxar.extract(nx, None, str(out))
    assert (out / 'exefs' / 'main').read_bytes() == MAIN
    assert (out / 'exefs' / 'main.npdm').read_bytes() == b'META'
    assert (out / 'romfs' / 'big.bin').read_bytes() == BIG, 'a file of several blocks, zstd'
    assert (out / 'romfs' / 'empty.bin').read_bytes() == b''
    assert (out / 'romfs' / 'Model' / 'a.bfres.zs').read_bytes() == b'\x28\xb5\x2f\xfd' + b'model' * 9
    assert not (out / 'romfs' / 'base_only.bin').exists(), "a snapshot is a whole view: the base's files are not added"
    assert not (out / 'romfs' / 'dlc.bin').exists()
    assert nup.read_heads(str(out / nup.HEADS_NAME)) == [], "nup.py's list of damaged .zs files is written"

    raw = archive(GAME)
    path.write_bytes(raw)
    nx = nxar.Nx(str(path))
    with nx.f:
        assert nx.read(next(r for rel, r in nx.walk(nx.titles[1]['romfs']) if rel == 'big.bin')) == BIG, 'raw blocks'

    # Header slots: the valid one with the highest generation
    def generation(blob):
        path.write_bytes(blob)
        nx = nxar.Nx(str(path))
        nx.f.close()
        return nx.generation

    newer = bytearray(good)
    struct.pack_into('<Q', newer, 4096 + 216, 1)
    seal(newer, 1)
    assert generation(newer) == 1, 'slot B with the higher generation'
    damaged = bytearray(newer)
    damaged[4096 + 100] ^= 1
    assert generation(damaged) == 0, 'a slot with a bad CRC is left out'
    damaged[100] ^= 1
    assert 'header' in refused(damaged, path), 'both slots damaged'
    fallback = bytearray(newer)
    fallback[4096 + 152] ^= 1   # (the newer generation's manifest hash)
    seal(fallback, 1)
    assert generation(fallback) == 0, "a newer generation whose metadata is damaged falls back to the older one"
    twins = bytearray(good)
    struct.pack_into('<H', twins, 4096 + 14, 1)   # (an optional feature bit: still a valid header)
    seal(twins, 1)
    refused(twins, path)   # (one generation, two different headers)

    # Damage
    header = struct.unpack_from('<4sHHIHH13Q', good, 0)
    manifest_at, index_at, data_size = header[13], header[15], header[12]
    broken = bytearray(good)
    broken[manifest_at + 40] ^= 1
    assert 'manifest' in refused(broken, path).lower()
    assert 'incomplete' in refused(good[:-10], path)
    newer_format = bytearray(good)
    for slot in (0, 1):
        struct.pack_into('<H', newer_format, slot * 4096 + 4, 1)
        seal(newer_format, slot)
    assert 'version' in refused(newer_format, path)

    def with_index(change):
        """The archive with its block index changed and hashed again"""
        blob = bytearray(good)
        change(blob)
        count, checks_at, checks_size = header[16], header[17], header[18]
        digest = hashlib.sha256(bytes(blob[index_at:index_at + 24 * count]) + bytes(blob[checks_at:checks_at + checks_size])).digest()
        for slot in (0, 1):
            blob[slot * 4096 + 184:slot * 4096 + 216] = digest
            seal(blob, slot)
        return blob

    blocks = range(index_at, index_at + 24 * header[16], 24)   # (every block: the newest title's are among them)
    outside = with_index(lambda blob: [struct.pack_into('<Q', blob, at, 8192 + data_size) for at in blocks])
    refused(outside, path, extract=root / 'outside')   # (a block past the data region)
    longer = with_index(lambda blob: [struct.pack_into('<I', blob, at + 12, 65535) for at in blocks])
    refused(longer, path, extract=root / 'longer')   # (a block that says another size than its place in the file)
    flipped = bytearray(raw)
    flipped[flipped.index(MAIN) + 5] ^= 1   # (in the update's main, stored as is)
    assert 'damaged' in refused(flipped, path, extract=root / 'flipped'), "a file is checked against the archive's SHA-256"

    # What is not a game stored as exefs and romfs trees
    native = archive([(0, 65536, True, {'0123456789abcdef.nca': b'NCA3' + bytes(64)})])
    message = refused(native, path, extract=root / 'native')
    assert 'nxconvert extract' in message, message
    assert not (root / 'native').exists(), 'nothing is written for an archive that is refused'
    refused(archive(GAME[2:]), path, extract=root / 'dlc')   # (add-on content alone)
    looped = archive([(0, 1, True, {'exefs': {'main': MAIN}, 'romfs': {'again': {}}})])
    struct.pack_into('<II', looped, struct.unpack_from('<Q', looped, 72)[0] + 96 + 16 * 3, 3, 1)   # ('again' holds its own entry)
    for slot in (0, 1):
        at = struct.unpack_from('<QQ', looped, 72)
        looped[slot * 4096 + 152:slot * 4096 + 184] = hashlib.sha256(bytes(looped[at[0]:at[0] + at[1]])).digest()
        seal(looped, slot)
    refused(looped, path, extract=root / 'looped')   # (a directory reached twice)

    # A zstd block of fewer than 18 bytes (a small file that compresses well) is valid
    tiny = b'a' * 100
    assert len(zstandard.ZstdCompressor().compress(tiny)) < 18
    path.write_bytes(archive([(0, 1, True, {'exefs': {'main': MAIN}, 'romfs': {'tiny.bin': tiny}})], packed={'tiny.bin'}))
    nx = nxar.Nx(str(path))
    with nx.f:
        assert nx.read(next(r for _, r in nx.walk(nx.titles[0]['romfs']))) == tiny

    # A name that is not UTF-8, below the snapshot's top directory: refused, not a traceback
    named = archive([(0, 1, True, {'exefs': {'main': MAIN}, 'romfs': {'Deep': {'BADNAME': b'x'}}})])
    named[named.index(b'BADNAME')] = 0xff
    for slot in (0, 1):
        at = struct.unpack_from('<QQ', named, 72)
        named[slot * 4096 + 152:slot * 4096 + 184] = hashlib.sha256(bytes(named[at[0]:at[0] + at[1]])).digest()
        seal(named, slot)
    assert 'UTF-8' in refused(named, path, extract=root / 'named')

    # The command, as make_game.py runs it
    path.write_bytes(good)
    output = io.StringIO()
    with redirect_stdout(output):
        assert not nxar.main([str(path), '--extract', str(root / 'probe'), '--only', 'exefs'])
    assert (root / 'probe' / 'exefs' / 'main').read_bytes() == MAIN
    assert not (root / 'probe' / 'romfs').exists()
    assert 'v131072' in output.getvalue(), output.getvalue()

print('PASS: .nx header slots, snapshots, raw and zstd blocks, refusals, and extraction through nup.py')
