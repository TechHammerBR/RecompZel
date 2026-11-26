"""Read a .nx archive (NXFormat: a decrypted Switch dump as nxconvert packs it, e.g. from a .nup) and extract it.

    python -I nx2/nxar.py <file.nx>                      list the game's versions in it
    python -I nx2/nxar.py <file.nx> --extract <dir> [--title <n|version>] [--only exefs|romfs]

The format is github.com/fab918/nxformat's docs/SPEC.md (NX 0.2 and 0.3; little-endian). What is read of it here:
    0, 4096  two copies of a 256-byte "NXAR" header with a CRC-32C: the valid one with the highest generation counts
    8192     the data: blocks of at most 1 MiB, each stored as is or as one zstd frame
    then     the catalog "NXCT" (applications, programs, and the snapshots: a version of the game each, with its
             root directory), the manifest "NXMF" (directories, their entries, files, the blocks of each file, names),
             the block index (24 bytes a block) and a table of CRCs. The header holds the SHA-256 of the catalog, of
             the manifest, and of the block index with the CRC table; the manifest holds each file's SHA-256.
A snapshot is a whole view: an update's tree holds the base's files too, so the newest one is extracted alone.
Only a game stored as exefs/ and romfs/ trees is read (nxconvert pack-nup, pack-tree). One stored as NCA files
(nxconvert pack, from a DNSP or DXCI) is refused: nxconvert extract makes the folders from it.
The extraction itself is nup.py's (extract: its path checks, its progress, its list of damaged .zs files).
"""
import argparse
import hashlib
import io
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nup

NONE = 0xffffffff
HEADER = struct.Struct("<4sHHIHH13Q32s32s32sQI24sI")
BLOCK = struct.Struct("<QIIBBH")
PROGRAM_TYPES = (0, 1, 3)   # (base, update, standalone update; 2 is add-on content)

_CRC = []
for _i in range(256):
    for _ in range(8):
        _i = _i >> 1 ^ 0x82f63b78 if _i & 1 else _i >> 1
    _CRC.append(_i)


def crc32c(data):
    crc = 0xffffffff
    for b in data:
        crc = _CRC[(crc ^ b) & 0xff] ^ crc >> 8
    return crc ^ 0xffffffff


class Nx:
    """A .nx archive with what nup.extract, nup.pick_title and nup.heal use of a Nup: titles (the snapshots that are
    a version of the game), walk, copy_to, read, files and file_details. A file's record is (file id, 0, size, first
    block reference, blocks, chunk size log2)"""
    def __init__(self, path):
        self.path = path
        self.f = open(path, "rb")
        try:
            self._open()
        except BaseException:
            self.f.close()
            raise

    def fail(self, what):
        raise SystemExit("%s: %s" % (self.path, what))

    def _open(self):
        have = os.fstat(self.f.fileno()).st_size
        page = self.f.read(8192)
        slots, unknown = [], None
        for at in (0, 4096):
            raw = page[at:at + 256]
            if len(raw) != 256 or raw[:4] != b"NXAR" or crc32c(raw[:252]) != struct.unpack_from("<I", raw, 252)[0]:
                continue
            h = HEADER.unpack(raw)
            if h[1] != 0 or h[2] not in (2, 3) or h[3] != 256 or h[4] != 1 or h[23] != 16384:
                unknown = "NX format version %d.%d (features %#x) is not one this reader knows (0.2 and 0.3)" % (h[1], h[2], h[4])
                continue
            slots.append((h[22], raw, h))
        if not slots:
            if page[:4] != b"NXAR" and page[4096:4100] != b"NXAR":
                self.fail("not a .nx archive (magic %r)" % page[:4])
            self.fail(unknown or "both copies of the .nx header are damaged")
        slots.sort(key=lambda s: s[0], reverse=True)
        if len(slots) == 2 and slots[0][0] == slots[1][0] and slots[0][1] != slots[1][1]:
            self.fail("the two copies of the .nx header disagree")
        error = None
        for generation, _, h in slots:   # (a newer generation whose metadata is damaged: the older one, as the format says)
            try:
                self._mount(h, have)
                self.generation = generation
                return
            except SystemExit as e:
                error = error or e
        raise error

    def _section(self, what, at, size, least, limit):
        if at % 16 or size < least or at < 8192 or at + size > limit:
            self.fail("the %s is outside the .nx archive" % what)
        self.f.seek(at)
        data = self.f.read(size)
        if len(data) != size:
            self.fail("the %s ends early" % what)
        return data

    def _mount(self, h, have):
        (size, catalog_at, catalog_size, _, _, self.data_at, data_size, manifest_at, manifest_size, index_at,
         self.block_count, checks_at, checks_size) = h[6:19]
        if have < size:
            raise SystemExit("the .nx file is incomplete: it is %d MB, its header says %d MB. Download or copy it again "
                             "(wait for the copy to finish) and check that the drive had room" % (have >> 20, size >> 20))
        self.file_size = size
        self.data_end = self.data_at + data_size
        if self.block_count and (self.data_at != 8192 or self.data_end > size):
            self.fail("the data is outside the .nx archive")
        catalog = self._section("catalog", catalog_at, catalog_size, 128, size)
        if hashlib.sha256(catalog).digest() != h[19]:
            self.fail("the catalog is damaged (its SHA-256 differs)")
        manifest = self._section("manifest", manifest_at, manifest_size, 96, size)
        if hashlib.sha256(manifest).digest() != h[20]:
            self.fail("the manifest is damaged (its SHA-256 differs)")
        self.index = self._section("block index", index_at, 24 * self.block_count, 0, size) if self.block_count else b""
        digest = hashlib.sha256(self.index)
        if self.block_count:
            if checks_at % 16 or checks_at + checks_size > size:
                self.fail("the integrity table is outside the .nx archive")
            self.f.seek(checks_at)
            left = checks_size
            while left:
                b = self.f.read(min(left, 8 << 20))
                if not b:
                    self.fail("the integrity table ends early")
                digest.update(b)
                left -= len(b)
        if digest.digest() != h[21]:
            self.fail("the block index is damaged (its SHA-256 differs)")
        try:
            self._manifest(manifest)
            self._catalog(catalog)
        except (struct.error, IndexError, UnicodeDecodeError) as e:
            self.fail("the .nx archive's tables are not as the format says (%s)" % e)

    def _table(self, what, data, at, count, each):
        if count and (at < 96 or at + count * each > len(data)):
            self.fail("the %s table is outside its section" % what)
        return at

    def _manifest(self, m):
        (magic, version, header, total, self.nd, self.nf, self.ne, self.nr,
         dirs_at, files_at, entries_at, refs_at, pool_at, pool_size) = struct.unpack_from("<4sHHQIIIIQQQQQQ", m, 0)
        if magic != b"NXMF" or version != 1 or header != 96 or total != len(m) or not self.nd:
            self.fail("the manifest is not one this reader knows")
        self.m = m
        self.dirs_at = self._table("directory", m, dirs_at, self.nd, 16)
        self.entries_at = self._table("entry", m, entries_at, self.ne, 24)
        self._table("file", m, files_at, self.nf, 64)
        self._table("block reference", m, refs_at, self.nr, 4)
        if pool_at + pool_size > len(m):
            self.fail("the names are outside the manifest")
        self.pool = (pool_at, pool_at + pool_size)
        self.refs = struct.unpack_from("<%dI" % self.nr, m, refs_at) if self.nr else ()
        self.files, self.file_details = [], []
        for i in range(self.nf):
            at = files_at + 64 * i
            size, first, count, log2 = struct.unpack_from("<QIIB", m, at)
            if not 16 <= log2 <= 20 or count != -(-size // (1 << log2)) or first + count > self.nr:
                self.fail("file %d's blocks are not as the format says" % i)
            self.files.append((i, 0, size, first, count, log2))
            self.file_details.append((m[at + 20:at + 52], 0, b""))

    def _catalog(self, c):
        (magic, version, header, total, _, na, np, ns, _, _, _, _, apps_at, _, snaps_at) = struct.unpack_from("<4sHHQ8I3Q", c, 0)
        if magic != b"NXCT" or version != 1 or header != 128 or total != len(c):
            self.fail("the catalog is not one this reader knows")
        if apps_at < 128 or apps_at + 80 * na > len(c) or snaps_at < 128 or snaps_at + 120 * ns > len(c):
            self.fail("the catalog's tables are outside it")
        owner = {}
        for i in range(na):
            app, first, count = struct.unpack_from("<Q12xII", c, apps_at + 80 * i)
            owner.update((s, app) for s in range(first, min(first + count, ns)))
        self.titles = []
        for i in range(ns):
            program, kind, _, _, ver, root = struct.unpack_from("<IBBHII", c, snaps_at + 120 * i)
            if program == NONE or kind not in PROGRAM_TYPES:
                continue
            if root >= self.nd:
                self.fail("snapshot %d's root directory is not in the manifest" % i)
            top = {name: target for name, kind, target in self.entries(root) if kind == 1}
            self.titles.append(dict(index=i, id=owner.get(i, 0), version=ver, type=kind, root=root,
                                    exefs=top.get("exefs", NONE), romfs=top.get("romfs", NONE)))

    def entries(self, d):
        """(name, kind, target) of each entry of directory d: kind 1 a directory, 2 a file"""
        first, count = struct.unpack_from("<II", self.m, self.dirs_at + 16 * d)
        if first + count > self.ne:
            self.fail("directory %d's entries are outside the table" % d)
        for i in range(first, first + count):
            at, n, target, kind = struct.unpack_from("<QIIB", self.m, self.entries_at + 24 * i)
            if at < self.pool[0] or at + n > self.pool[1] or kind not in (1, 2) or target >= (self.nd if kind == 1 else self.nf):
                self.fail("entry %d of the manifest is not as the format says" % i)
            try:
                name = self.m[at:at + n].decode("utf-8")
            except UnicodeDecodeError:
                self.fail("entry %d of the manifest has a name that is not UTF-8" % i)
            yield name, kind, target

    def walk(self, d, prefix=""):
        """(relative path, file record) for every file under directory d; nothing for a directory that is not there"""
        if d == NONE:
            return
        seen = set()
        pending = [(d, prefix)]
        while pending:
            d, prefix = pending.pop()
            if d in seen:
                self.fail("a directory is reached twice in one snapshot")
            seen.add(d)
            for name, kind, target in self.entries(d):
                if kind == 1:
                    pending.append((target, prefix + name + "/"))
                else:
                    yield prefix + name, self.files[target]

    def copy_to(self, r, g, name="", *, packed=None):
        """The file into the open file g, checked against its SHA-256. packed is nup.py's and means nothing here"""
        i, _, left, first, count, log2 = r
        digest = hashlib.sha256()
        for ref in self.refs[first:first + count]:
            if ref >= self.block_count:
                self.fail("a file names a block that is not in the index")
            at, stored, logical, codec, flags, _ = BLOCK.unpack_from(self.index, 24 * ref)
            # (stored capped: a block reads at most a little more than its 1 MiB, whatever the index says)
            if (logical != min(left, 1 << log2) or not stored or at < self.data_at or at + stored > self.data_end or codec > 1
                    or stored > (logical + 1024 if codec else logical)):
                self.fail("block %d is not as the format says" % ref)
            self.f.seek(at)
            b = self.f.read(stored)
            if len(b) != stored:
                self.fail("the .nx file ends early: it is incomplete. Download or copy it again")
            if codec:
                import zstandard
                try:   # (the stated size also keeps a frame from claiming more memory than a block)
                    if zstandard.get_frame_parameters(b).content_size != logical:
                        self.fail("block %d's zstd frame does not state the block's size" % ref)
                    b = zstandard.ZstdDecompressor().decompress(b)
                except zstandard.ZstdError as e:
                    self.fail("block %d does not decompress (%s): the archive is damaged" % (ref, e))
            if len(b) != logical:
                self.fail("block %d came out as %d bytes, %d expected" % (ref, len(b), logical))
            digest.update(b)
            g.write(b)
            left -= logical
        if digest.digest() != self.file_details[i][0]:
            self.fail("%s is damaged in the archive (its SHA-256 differs). Copy or convert the file again" % (name or "file %d" % i))

    def read(self, r, n=None):
        b = io.BytesIO()
        self.copy_to(r, b)
        return b.getvalue() if n is None else b.getvalue()[:n]


def pick_title(nx, want):
    """nup.pick_title (the newest version, or the one asked for), for a game stored as exefs and romfs trees"""
    if not nx.titles:
        raise SystemExit("%s holds no game: only add-on content, or nothing with a program" % nx.path)
    t = nup.pick_title(nx, want)
    if t["exefs"] == NONE:
        raise SystemExit("%s holds the game as NCA files (made by nxconvert pack from a DNSP or DXCI), which Hookshot "
                         "does not read. Run \"nxconvert extract <file.nx> <new folder>\" and choose the folder that has "
                         "romfs and exefs in it, or convert your .nup with nxconvert pack-nup" % nx.path)
    return t


def extract(nx, want, out, only=None):
    """Title want (None: the newest) to out/exefs and out/romfs, its modules made plain NSOs as nup.py does"""
    t = pick_title(nx, want)
    print("extracting title %d (v%d) to %s" % (t["index"], t["version"], out))
    n, total = nup.extract(nx, t, out, only)
    print("done: %d files written, %.2f GB" % (n, total / 1e9))
    if only != "romfs":
        nup.plain_modules(nx, t, out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("nx")
    ap.add_argument("--extract", metavar="DIR")
    ap.add_argument("--title", help="index, version or application id (default: the newest version)")
    ap.add_argument("--only", choices=("exefs", "romfs"))
    a = ap.parse_args(argv)
    nx = Nx(a.nx)
    with nx.f:
        print("%s: %.2f GB, %d dirs, %d files, %d blocks" % (os.path.basename(a.nx), nx.file_size / 1e9, nx.nd, nx.nf, nx.block_count))
        for t in nx.titles:
            ex = list(nx.walk(t["exefs"]))
            ro = list(nx.walk(t["romfs"]))
            print("title %d: %016x v%d  exefs %d files (%s)  romfs %d files, %.2f GB" % (
                t["index"], t["id"], t["version"], len(ex), ", ".join("%s %d" % (p, r[2]) for p, r in ex),
                len(ro), sum(r[2] for _, r in ro) / 1e9))
        if a.extract:
            extract(nx, a.title, a.extract, a.only)


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):   # (-I ignores PYTHONIOENCODING: a file's name in other letters crashed a print)
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    sys.exit(main())
