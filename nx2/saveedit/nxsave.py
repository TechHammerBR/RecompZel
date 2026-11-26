"""Reading and writing the game's save files (account.sav, option.sav, slot_NN/progress.sav, slot_NN/caption.sav), and
the names of their entries from the player's own game files.

A save file is a table of (hash, value) pairs grouped by type, then a data section:

    0x00  u32 magic 0x01020304, u32 version, u32 offset of the data section, zeros to 0x20
    0x20  pairs of u32: (0, type number) starts a type's group; (hash, value) is one entry of the current type.
          A small value (on/off, number, float, enum) is the value itself; any other is an offset into the file.
    data  texts are fixed-size and NUL-ended, a list is a u32 count then its items, a binary is a u32 size then bytes.

Nothing is ever moved or resized: an edit overwrites a value in place, so the file keeps its size and layout.

The names of the entries are not in the save (only murmur3 hashes of them). They are recovered from the game files
(romfs in the game folder) the first time and kept in the game folder's cache/save-names.json.

Adapted from an MIT-licensed save editor (see LICENSE in this folder).
"""
import json
import os
import re
import struct
import time
from pathlib import Path

try:
    import compression.zstd as zstd     # Python 3.14+
except ImportError:                      # pragma: no cover
    zstd = None

MAGIC = 0x01020304
TYPES = ['Bool', 'BoolArray', 'Int', 'IntArray', 'Float', 'FloatArray', 'Enum', 'EnumArray', 'Vector2', 'Vector2Array',
         'Vector3', 'Vector3Array', 'String16', 'String16Array', 'String32', 'String32Array', 'String64',
         'String64Array', 'Binary', 'BinaryArray', 'UInt', 'UIntArray', 'Int64', 'Int64Array', 'UInt64', 'UInt64Array',
         'WString16', 'WString16Array', 'WString32', 'WString32Array', 'WString64', 'WString64Array', 'Bool64bitKey']
INLINE = {'Bool', 'Int', 'UInt', 'Float', 'Enum'}
READ_ONLY = {'Binary', 'BinaryArray', 'Bool64bitKey'}
# an item of the type: (struct format, size in bytes); texts are handled apart
ITEM = {'Int': ('<i', 4), 'UInt': ('<I', 4), 'Float': ('<f', 4), 'Enum': ('<I', 4), 'Int64': ('<q', 8),
        'UInt64': ('<Q', 8), 'Vector2': ('<2f', 8), 'Vector3': ('<3f', 12)}
RANGE = {'Int': (-2**31, 2**31 - 1), 'UInt': (0, 2**32 - 1), 'Int64': (-2**63, 2**63 - 1), 'UInt64': (0, 2**64 - 1)}


def murmur3(b):
    h = 0
    n = len(b) & ~3
    for (k,) in struct.iter_unpack('<I', b[:n]):
        k = (k * 0xcc9e2d51) & 0xffffffff
        k = ((k << 15) | (k >> 17)) & 0xffffffff
        k = (k * 0x1b873593) & 0xffffffff
        h ^= k
        h = ((h << 13) | (h >> 19)) & 0xffffffff
        h = (h * 5 + 0xe6546b64) & 0xffffffff
    if len(b) > n:
        k = int.from_bytes(b[n:], 'little')
        k = (k * 0xcc9e2d51) & 0xffffffff
        k = ((k << 15) | (k >> 17)) & 0xffffffff
        k = (k * 0x1b873593) & 0xffffffff
        h ^= k
    h ^= len(b)
    h ^= h >> 16
    h = (h * 0x85ebca6b) & 0xffffffff
    h ^= h >> 13
    h = (h * 0xc2b2ae35) & 0xffffffff
    return h ^ (h >> 16)


# ---------------------------------------------------------------------------------------------- the save file

def _text_size(t):
    """(bytes of one text, wide) for a text type or a list of them, else None."""
    m = re.match(r'^(W?)String(\d+)(Array)?$', t)
    return (int(m.group(2)) * (2 if m.group(1) else 1), bool(m.group(1))) if m else None


class Entry:
    __slots__ = ('hash', 'type', 'pos', 'raw', 'value', 'original')

    def __init__(self, hash_, type_, pos, raw):
        self.hash, self.type, self.pos, self.raw = hash_, type_, pos, raw
        self.value = self.original = None

    @property
    def is_list(self):
        return self.type.endswith('Array')

    @property
    def base(self):
        return self.type[:-5] if self.is_list else self.type

    @property
    def editable(self):
        return self.type not in READ_ONLY

    @property
    def changed(self):
        return self.value != self.original


class SaveFile:
    def __init__(self, path):
        self.path = Path(path)
        self.buf = bytearray(self.path.read_bytes())
        self.entries = []
        self._parse()

    def _parse(self):
        b = self.buf
        if len(b) < 0x20:
            raise ValueError('not a save file: too small')
        magic, self.version, self.data_off = struct.unpack_from('<III', b, 0)
        if magic != MAGIC or not 0x20 <= self.data_off <= len(b):
            raise ValueError('not a save file of this game')
        cur = None
        for pos in range(0x20, self.data_off - 7, 8):
            h, v = struct.unpack_from('<II', b, pos)
            if h == 0:
                if v >= len(TYPES):
                    raise ValueError(f'unknown type number {v} at 0x{pos:x}')
                cur = TYPES[v]
                continue
            if cur is None:
                raise ValueError('an entry before any type')
            e = Entry(h, cur, pos + 4, v)
            e.value = e.original = self._read(e)
            self.entries.append(e)

    # -- reading
    def _read_item(self, base, off):
        b = self.buf
        ts = _text_size(base)
        if ts:
            size, wide = ts
            raw = bytes(b[off:off + size])
            if wide:
                return raw.decode('utf-16-le', 'replace').split('\0')[0]
            return raw.split(b'\0')[0].decode('utf-8', 'replace')
        fmt, _ = ITEM[base]
        v = struct.unpack_from(fmt, b, off)
        return v[0] if len(v) == 1 else tuple(v)

    def _item_size(self, base):
        ts = _text_size(base)
        return ts[0] if ts else ITEM[base][1]

    def _read(self, e):
        b, v, t = self.buf, e.raw, e.type
        if t == 'Bool':
            return bool(v)
        if t in INLINE:
            return struct.unpack(ITEM[t][0], struct.pack('<I', v))[0]
        if not self.data_off <= v <= len(b) - 4 and t != 'Bool64bitKey':
            raise ValueError(f'entry {e.hash:08x}: offset 0x{v:x} is outside the file')
        if t == 'Binary':
            n, = struct.unpack_from('<I', b, v)
            return bytes(b[v + 4:v + 4 + n])
        if t in ('BinaryArray', 'Bool64bitKey'):
            return None
        if not e.is_list:
            return self._read_item(t, v)
        n, = struct.unpack_from('<I', b, v)
        if t == 'BoolArray':
            if v + 4 + (n + 7) // 8 > len(b):
                raise ValueError(f'entry {e.hash:08x}: the list runs past the end of the file')
            return tuple(bool(b[v + 4 + i // 8] >> (i % 8) & 1) for i in range(n))
        size = self._item_size(e.base)
        if v + 4 + n * size > len(b):
            raise ValueError(f'entry {e.hash:08x}: the list runs past the end of the file')
        return tuple(self._read_item(e.base, v + 4 + i * size) for i in range(n))

    def extent(self, e):
        """(offset, size) of the entry's bytes in the data section, None for a value kept in the table."""
        if e.type in INLINE or e.type in ('BinaryArray', 'Bool64bitKey'):
            return None
        if e.type == 'Binary':
            return e.raw, 4 + len(e.value)
        if not e.is_list:
            return e.raw, self._item_size(e.type)
        if e.type == 'BoolArray':
            return e.raw, 4 + (len(e.value) + 7) // 8
        return e.raw, 4 + len(e.value) * self._item_size(e.base)

    # -- writing
    def _pack_item(self, base, value):
        ts = _text_size(base)
        if ts:
            size, wide = ts
            raw = value.encode('utf-16-le' if wide else 'utf-8')
            if len(raw) > size - (2 if wide else 1):
                raise ValueError(f'the text is too long: at most {size // (2 if wide else 1) - 1} characters')
            return raw.ljust(size, b'\0')
        fmt, _ = ITEM[base]
        if base in RANGE:
            lo, hi = RANGE[base]
            if not lo <= value <= hi:
                raise ValueError(f'{value} is out of range ({lo} to {hi})')
        return struct.pack(fmt, *value) if isinstance(value, tuple) else struct.pack(fmt, value)

    def set(self, e, value):
        """Change an entry's value in the buffer. A list keeps its length."""
        if not e.editable:
            raise ValueError('this kind of entry cannot be edited')
        b = self.buf
        if e.type == 'Bool':
            struct.pack_into('<I', b, e.pos, 1 if value else 0)
            e.raw = 1 if value else 0
        elif e.type in INLINE:
            raw = self._pack_item(e.type, value)
            b[e.pos:e.pos + 4] = raw
            e.raw, = struct.unpack('<I', raw)
        elif not e.is_list:
            raw = self._pack_item(e.type, value)
            b[e.raw:e.raw + len(raw)] = raw
        else:
            value = tuple(value)
            if len(value) != len(e.value):
                raise ValueError(f'the list must keep its {len(e.value)} items')
            if e.type == 'BoolArray':
                bits = bytearray((len(value) + 7) // 8)
                for i, x in enumerate(value):
                    if x:
                        bits[i // 8] |= 1 << (i % 8)
                b[e.raw + 4:e.raw + 4 + len(bits)] = bits
            else:
                raw = b''.join(self._pack_item(e.base, x) for x in value)
                b[e.raw + 4:e.raw + 4 + len(raw)] = raw
        e.value = self._read(e)

    @property
    def dirty(self):
        return any(e.changed for e in self.entries)

    def save(self, backup_dir=None):
        """Write the file (through a temporary file), after copying the one on disk into backup_dir."""
        if backup_dir:
            dst = Path(backup_dir) / time.strftime('%Y-%m-%d %H%M%S') / self.path.parent.name / self.path.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(self.path.read_bytes())
        tmp = self.path.with_name(self.path.name + '.editing')
        tmp.write_bytes(self.buf)
        tmp.replace(self.path)
        for e in self.entries:
            e.original = e.value


# ------------------------------------------------------------------------------------ names, from the game files

class Romfs:
    """The game's files in the game folder: the files themselves under romfs/ (as the Builder unpacks them), or one
    packed file (romfs/romfs.bin with romfs/index.json)."""

    def __init__(self, game):
        self.folder = folder = Path(game) / 'romfs'
        self.bin = None
        if (folder / 'index.json').is_file():
            index = json.loads((folder / 'index.json').read_text(encoding='utf-8'))
            self.files = index['files']
            self.sha = index.get('romfs_sha256', '')
            self.bin = open(folder / 'romfs.bin', 'rb')
        elif folder.is_dir():
            self.files = []
            for root, _dirs, names in os.walk(folder):
                for n in names:
                    p = Path(root) / n
                    rel = p.relative_to(folder).as_posix()
                    self.files.append({'path': rel, 'size': p.stat().st_size, 'offset': None})
            self.files.sort(key=lambda f: f['path'])
            self.sha = 'loose:' + romfs_marker(game, len(self.files))
        else:
            raise FileNotFoundError(f'no game files in {folder}')
        self.by_path = {f['path']: f for f in self.files}

    def load(self, f):
        if isinstance(f, str):
            f = self.by_path[f]
        if self.bin is None:
            return (self.folder / f['path']).read_bytes()
        self.bin.seek(f['offset'])
        return self.bin.read(f['size'])

    def close(self):
        if self.bin:
            self.bin.close()


def sarc_members(p):
    if p[:4] != b'SARC':
        raise ValueError('not an archive')
    head, = struct.unpack_from('<H', p, 4)
    data, = struct.unpack_from('<I', p, 12)
    count, = struct.unpack_from('<H', p, head + 6)
    names = head + 12 + count * 16 + 8
    out = {}
    for i in range(count):
        _, attr, lo, hi = struct.unpack_from('<IIII', p, head + 12 + i * 16)
        s = names + (attr & 0xffffff) * 4
        out[p[s:p.index(b'\0', s)].decode()] = p[data + lo:data + hi]
    return out


def byml(p):
    """A BYML file as Python values (either byte order)."""
    if p[:2] not in (b'YB', b'BY'):
        raise ValueError('not a BYML file')
    E, order = ('<', 'little') if p[:2] == b'YB' else ('>', 'big')
    _, keys, strs, root = struct.unpack_from(E + 'HIII', p, 2)

    def table(off):
        if not off:
            return []
        n = int.from_bytes(p[off + 1:off + 4], order)
        offs = struct.unpack_from(f'{E}{n}I', p, off + 4)
        return [p[off + o:p.index(b'\0', off + o)].decode('utf-8', 'replace') for o in offs]

    K, S = table(keys), table(strs)
    u32 = struct.Struct(E + 'I')

    def node(t, v):
        if t == 0xa0:
            return S[v]
        if t == 0xd0:
            return bool(v)
        if t == 0xd1:
            return v - (1 << 32) if v & 0x80000000 else v
        if t == 0xd2:
            return struct.unpack(E + 'f', u32.pack(v))[0]
        if t == 0xd3:
            return v
        if t == 0xd4:
            return struct.unpack_from(E + 'q', p, v)[0]
        if t == 0xd5:
            return struct.unpack_from(E + 'Q', p, v)[0]
        if t == 0xd6:
            return struct.unpack_from(E + 'd', p, v)[0]
        if t == 0xff:
            return None
        if t in (0xa1, 0xa2):
            n, = u32.unpack_from(p, v)
            return p[v + 4:v + 4 + n] if t == 0xa1 else p[v + 8:v + 8 + n]
        n = int.from_bytes(p[v + 1:v + 4], order)
        if t == 0xc0:
            vo = v + 4 + ((n + 3) & ~3)
            vals = struct.unpack_from(f'{E}{n}I', p, vo)
            return [node(p[v + 4 + i], vals[i]) for i in range(n)]
        if t == 0xc1:
            d = {}
            for i in range(n):
                e = v + 4 + 8 * i
                d[K[int.from_bytes(p[e:e + 3], order)]] = node(p[e + 3], u32.unpack_from(p, e + 4)[0])
            return d
        if t == 0x20:
            d = {}
            for i in range(n):
                k, val = struct.unpack_from(E + 'II', p, v + 4 + 8 * i)
                d[k] = node(p[v + 4 + 8 * n + i], val)
            return d
        raise ValueError(f'BYML node type 0x{t:x}')

    return node(p[root], root)


# Folders of pictures, sound, models and terrain: big, and without names in them.
SKIP_TOP = {'Tex', 'TerrainArc', 'Model', 'Sound', 'Bake', 'Phive', 'PreComputedCulling', 'Foliage', 'Effect', 'Voice',
            'Shader', 'Font2', 'Movie', 'Lib'}
NAME_RUN = re.compile(rb'[A-Za-z0-9_.]{4,96}')
CACHE_VERSION = 1


def build_names(game=None, progress=lambda text: None):
    """{'names': {hash: name}, 'enums': {flag hash: [[value hash, name], ...]}, 'enum_values': {hash: name}}, read
    from the game's files: the game's list of save entries gives the hashes, and every run of name characters in the
    game's data files is hashed and looked up among them. Grouped entries are named 'Group.Member'."""
    if zstd is None:
        raise RuntimeError('this needs Python 3.14 or later (compression.zstd)')
    rom = Romfs(game)
    try:
        progress('Reading the game\'s list of save entries...')
        dics = {k: zstd.ZstdDict(v) for k, v in sarc_members(zstd.decompress(rom.load('Pack/ZsDic.pack.zs'))).items()}
        plain = dics['zs.zsdic']
        lists = sorted(p for p in rom.by_path if re.fullmatch(r'GameData/GameDataList\.Product\.\d+\.byml\.zs', p))
        if not lists:
            raise RuntimeError('the game files have no GameData/GameDataList')
        data = byml(zstd.decompress(rom.load(lists[-1]), zstd_dict=plain))['Data']

        want, structs, enums, enum_values = set(), {}, {}, {}
        for t, entries in data.items():
            if t == 'Bool64bitKey':
                continue
            for e in entries:
                want.add(e['Hash'])
                if t == 'Struct':
                    structs[e['Hash']] = [(m['Hash'], m['Value']) for m in e.get('DefaultValue') or []]
                elif t in ('Enum', 'EnumArray'):
                    vals, raws = e.get('Values') or [], e.get('RawValues') or []
                    pairs = [[v, r] for v, r in zip(vals, raws) if isinstance(v, int) and isinstance(r, str)]
                    enums[e['Hash']] = pairs
                    enum_values.update((v, r) for v, r in pairs)

        runs = set()
        todo = []
        for f in rom.files:
            p = f['path']
            top = p.split('/', 1)[0]
            if top in SKIP_TOP or (top == 'Event' and not p.startswith('Event/EventFlow/')) or f['size'] > 64 << 20:
                continue
            todo.append(f)
        for i, f in enumerate(todo):
            if i % 500 == 0:
                progress(f'Looking for names in the game files... {100 * i // len(todo)}%')
            raw, p = rom.load(f), f['path']
            if p.endswith('.zs'):
                d = (dics.get('pack.zsdic') if p.endswith('.pack.zs') else
                     dics.get('bcett.byml.zsdic') if p.endswith('.bcett.byml.zs') else None) or plain
                try:
                    raw = zstd.decompress(raw, zstd_dict=d)
                except Exception:
                    continue
            runs.update(NAME_RUN.findall(raw))
    finally:
        rom.close()

    progress('Matching names...')
    cands = set(runs)
    for s in runs:
        if b'.' in s:
            cands.update(x for x in s.split(b'.') if len(x) >= 2)
    by_hash = {}
    for s in cands:
        by_hash.setdefault(murmur3(s), s.decode('ascii'))
    names = {h: by_hash[h] for h in want if h in by_hash}

    # A group's member is named 'Group.Member': names spread from a named group to its members, and from a named
    # member back to its group, until nothing new is found. Every name is checked against its hash.
    parents = {}
    for s, members in structs.items():
        for mh, flag in members:
            parents.setdefault(flag, []).append((s, mh))
    changed = True
    while changed:
        changed = False
        for flag, name in list(names.items()):
            if '.' not in name:
                continue
            group, member = name.rsplit('.', 1)
            for s, mh in parents.get(flag, ()):
                if s not in names and murmur3(group.encode()) == s:
                    names[s] = group
                    changed = True
                if mh not in by_hash and murmur3(member.encode()) == mh:
                    by_hash[mh] = member
                    changed = True
        for s, members in structs.items():
            group = names.get(s)
            if not group:
                continue
            for mh, flag in members:
                member = by_hash.get(mh)
                if member and flag not in names and murmur3(f'{group}.{member}'.encode()) == flag:
                    names[flag] = f'{group}.{member}'
                    changed = True
    return {'version': CACHE_VERSION, 'romfs': rom.sha, 'entries': len(want),
            'names': {str(h): n for h, n in names.items()},
            'enums': {str(h): v for h, v in enums.items()},
            'enum_values': {str(h): n for h, n in enum_values.items()}}


class Names:
    def __init__(self, raw=None):
        raw = raw or {}
        self.names = {int(k): v for k, v in raw.get('names', {}).items()}
        self.enums = {int(k): [(int(a), b) for a, b in v] for k, v in raw.get('enums', {}).items()}
        self.enum_values = {int(k): v for k, v in raw.get('enum_values', {}).items()}
        self.total = raw.get('entries', 0)

    def name(self, h):
        return self.names.get(h) or f'#{h:08x}'

    def enum_text(self, value):
        return self.enum_values.get(value) or f'#{value:08x}'

    def enum_parse(self, text):
        text = text.strip()
        if re.fullmatch(r'#[0-9a-fA-F]{1,8}', text):
            return int(text[1:], 16)
        return murmur3(text.encode())


def load_names(game, progress=lambda text: None, rebuild=False):
    """The names, from the game folder's cache (cache/save-names.json) when it was made from the same game files, else
    read from the game files (a few minutes, once) and kept there. No game files: names are left as hashes."""
    game = Path(game)
    try:
        if (game / 'romfs' / 'index.json').is_file():
            sha = json.loads((game / 'romfs' / 'index.json').read_text(encoding='utf-8')).get('romfs_sha256', '')
        else:
            if not (game / 'romfs').is_dir():
                return Names()
            sha = 'loose:' + romfs_marker(game, sum(len(f) for _r, _d, f in os.walk(game / 'romfs')))
    except (OSError, ValueError):
        return Names()                     # no game files: the editor still works, with hashes for names
    mine = cache_file(game)
    if not rebuild:
        try:
            raw = json.loads(mine.read_text(encoding='utf-8'))
            if raw.get('version') == CACHE_VERSION and raw.get('romfs') == sha:
                return Names(raw)
        except (OSError, ValueError):
            pass
    raw = build_names(game, progress)
    try:
        mine.parent.mkdir(parents=True, exist_ok=True)
        mine.write_text(json.dumps(raw), encoding='utf-8')
    except OSError:
        pass
    return Names(raw)


def romfs_marker(game, count):
    """What tells one build's game files from another's: the build's version line (hookshot_version.txt), with the
    files' count. The same game files give the same marker, so a new build of the same game reads its names once."""
    try:
        version = (Path(game) / 'hookshot_version.txt').read_text(encoding='utf-8', errors='replace').strip()
    except OSError:
        version = ''
    return f'{version}|{count}'


def cache_file(game):
    """The names read from a game folder's files, kept in its cache folder"""
    return Path(game) / 'cache' / 'save-names.json'
