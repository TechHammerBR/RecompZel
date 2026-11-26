"""The launcher's save editor (builder/HookshotBuilder/SaveEditor.cs): one process for the page while it is open, one JSON
request a line on stdin and one JSON answer a line on stdout ({"ok": true, ...} or {"ok": false, "error": "..."}); while
the names are read from the game files the first time, lines {"progress": "..."} come before the answer.

A slot is held in memory as it is edited (the Stats, Inventory, Progress and All entries views all change the same files)
and written only by "save", after the files on disk are copied to save-backups/<date and time>/ in the game folder.
Close the game before saving: a running game writes over the save files when it saves.

    python -I nx2/saveedit/server.py --game <game folder> [--user <the launcher's user folder>]

Adapted from an MIT-licensed save editor (see LICENSE in this folder).
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # (python -I leaves this folder off the path)
import nxsave  # noqa: E402
import oot_catalog as cat  # noqa: E402

H = cat.h
MAX_ROWS = 20000


# ------------------------------------------------------------------------------------------------ values as text
def fmt_item(names, base, v):
    if base == 'Bool':
        return 'On' if v else 'Off'
    if base == 'Enum':
        return names.enum_text(v)
    if base == 'Float':
        return f'{v:.7g}'
    if isinstance(v, tuple):
        return ', '.join(f'{x:.7g}' for x in v)
    return str(v)


def fmt(names, e):
    if e.type == 'Binary':
        return f'({len(e.value)} bytes, not editable)'
    if e.value is None:
        return '(not editable)'
    if e.is_list:
        head = ' | '.join(fmt_item(names, e.base, x) for x in e.value[:6])
        return f'[{len(e.value)}] {head}{" | ..." if len(e.value) > 6 else ""}'
    return fmt_item(names, e.base, e.value)


def parse_item(names, e, base, text):
    text = text.strip()
    if base == 'Bool':
        low = text.lower()
        if low in ('on', 'true', '1', 'yes'):
            return True
        if low in ('off', 'false', '0', 'no'):
            return False
        raise ValueError(f'"{text}" is not On or Off')
    if base == 'Enum':
        v = names.enum_parse(text)
        allowed = names.enums.get(e.hash)
        if allowed and v not in {a for a, _ in allowed}:
            raise ValueError(f'"{text}" is not one of this entry\'s values')
        return v
    if base in nxsave.RANGE:
        try:
            return int(text, 0)
        except ValueError:
            raise ValueError(f'"{text}" is not a whole number') from None
    if base == 'Float':
        try:
            return float(text)
        except ValueError:
            raise ValueError(f'"{text}" is not a number') from None
    if base.startswith('Vector'):
        n = int(base[-1])
        try:
            parts = tuple(float(x) for x in text.replace(',', ' ').split())
        except ValueError:
            raise ValueError(f'"{text}" is not {n} numbers') from None
        if len(parts) != n:
            raise ValueError(f'{n} numbers are needed, separated by commas')
        return parts
    return text     # a text


# ------------------------------------------------------------------------------------------------- where saves are
def is_account_dir(d):
    d = Path(d)
    return d.is_dir() and (any(d.glob('slot_[0-9][0-9]')) or (d / 'option.sav').is_file() or (d / 'account.sav').is_file())


def save_bases(game, user):
    """The folders Hookshot keeps save accounts in: the launcher's user folder (%APPDATA%\\Hookshot, the game started
    with --user), then the game folder's own user\\save (the game started by itself)"""
    out = []
    if user:
        out.append(Path(user) / 'save')
    out.append(Path(game) / 'user' / 'save')
    return out


def accounts(game, user):
    found = []
    for base in save_bases(game, user):
        if base.is_dir():
            found += [d for d in base.iterdir() if is_account_dir(d)]
    return sorted(found, key=lambda d: max((f.stat().st_mtime for f in d.rglob('*.sav')), default=0), reverse=True)


def slot_files(account):
    """[(slot folder name, {kind: path})] of an account folder"""
    account = Path(account)
    shared = {k: account / f'{k}.sav' for k in ('option', 'account') if (account / f'{k}.sav').is_file()}
    out = []
    for d in sorted(account.glob('slot_[0-9][0-9]')):
        paths = {k: d / f'{k}.sav' for k in ('progress', 'caption') if (d / f'{k}.sav').is_file()}
        if 'progress' in paths:
            out.append((d.name, {**paths, **shared}))
    return out


def summary(paths):
    """A slot's line for the list: hearts, rupees, where, when saved (from caption.sav, the file-select screen's)"""
    out = {}
    try:
        sf = nxsave.SaveFile(paths.get('caption') or paths['progress'])
        by = {e.hash: e for e in sf.entries}
        get = lambda name: (by.get(H(name)) or by.get(name if isinstance(name, int) else -1))
        life, most = get('CaptionData.Life'), get('CaptionData.MaxLife')
        rupees = get('CaptionData.CurrentRupee')
        where = by.get(cat.CAPTION_MAP)
        if life is not None and most is not None:
            out['hearts'] = f'{life.value / 4:g} / {most.value / 4:g}'
        if rupees is not None:
            out['rupees'] = rupees.value
        if where is not None and isinstance(where.value, str):
            out['where'] = where.value.split('/')[-1]
    except (OSError, ValueError, KeyError):
        pass
    try:
        out['saved'] = time.strftime('%Y-%m-%d %H:%M', time.localtime(Path(paths['progress']).stat().st_mtime))
    except OSError:
        pass
    return out


# ---------------------------------------------------------------------------------------------------- the slot
class Slot:
    KINDS = ('progress', 'caption', 'option', 'account')

    def __init__(self, paths):
        self.paths = paths
        self.files, self.by_hash, self.errors = {}, {}, []
        for kind, path in paths.items():
            try:
                sf = nxsave.SaveFile(path)
            except (OSError, ValueError) as err:
                self.errors.append(f'{Path(path).name}: {err}')
                continue
            self.files[kind] = sf
            self.by_hash[kind] = {e.hash: e for e in sf.entries}

    def get(self, name, kind='progress'):
        return self.by_hash.get(kind, {}).get(name if isinstance(name, int) else H(name))

    def edited(self):
        return sum(e.changed for sf in self.files.values() for e in sf.entries)


class Editor:
    def __init__(self, game, user):
        self.game, self.user = Path(game), user
        self.names = nxsave.Names()
        self.names_loaded = False
        self.slot = None
        self.account = None

    # -- helpers, as the original's Stats tab has them
    def put(self, name, value, kind='progress'):
        e = self.slot.get(name, kind) if self.slot else None
        if e is None:
            return False
        if e.value != value:
            self.slot.files[kind].set(e, value)
        return True

    def val(self, name, kind='progress', default=None):
        e = self.slot.get(name, kind) if self.slot else None
        return default if e is None else e.value

    def bag_sizes(self, key):
        _k, _label, size_h, _name_h, _prefix, sizes = next(b for b in cat.BAGS if b[0] == key)
        now = self.val(size_h, default=0) or 0
        return now, [n for n in sizes if n >= now]

    def limit(self, item):
        _l, _i, bag, most = next(a for a in cat.AMOUNTS if a[1] == item)
        if bag:
            return self.bag_sizes(bag)[0]
        return most

    def write_vital(self, what, raw):
        _w, prog, cap, _u = next(x for x in cat.VITALS if x[0] == what)
        self.put(prog, raw)
        self.put(cap, raw, 'caption')

    def need_slot(self):
        if not self.slot:
            raise ValueError('Open a save slot first.')

    # -- requests
    def r_accounts(self, q):
        out = []
        for a in accounts(self.game, self.user):
            out.append({'path': str(a), 'slots': [{'slot': name, 'label': f'Slot {int(name[5:]) + 1}', **summary(paths)}
                                                  for name, paths in slot_files(a)]})
        return {'accounts': out}

    def r_names(self, q):
        if not self.names_loaded:
            self.names = nxsave.load_names(self.game, progress=lambda text: send({'progress': text}))
            self.names_loaded = True
        return {'named': len(self.names.names), 'total': self.names.total}

    def r_open(self, q):
        paths = dict(slot_files(q['account'])).get(q['slot'])
        if not paths:
            raise ValueError('That save slot is not there any more.')
        self.account, self.slot = Path(q['account']), Slot(paths)
        if 'progress' not in self.slot.files:
            errors = '; '.join(self.slot.errors)
            self.slot = None
            raise ValueError('The slot could not be read: ' + errors)
        return {'errors': self.slot.errors, 'edited': 0}

    def r_stats(self, q):
        self.need_slot()
        st = {}
        for what, prog, _cap, units in cat.VITALS:
            raw = self.val(prog)
            st[what] = None if raw is None else raw / units
        mp_max = (self.val('PlayerStatus.MPMax') or 0) / 10
        meter = min(range(len(cat.MAGIC_METERS)), key=lambda i: abs(cat.MAGIC_METERS[i][0] - mp_max))
        st['meters'] = [m[1] for m in cat.MAGIC_METERS]
        st['meter'] = meter
        wallet = self.val(cat.WALLET_NAME)
        st['wallets'] = [f'{w[1]} ({w[2]})' for w in cat.WALLETS]
        st['wallet'] = next((i for i, w in enumerate(cat.WALLETS) if w[0] == wallet), -1)
        st['rupees'] = self.val(cat.RUPEES)
        st['rupee_limit'] = self.val(cat.RUPEE_LIMIT) or 0
        child = self.val(cat.IS_CHILD)
        here = self.val(cat.CURRENT_MAP)
        st['age'] = None if child is None else ('young' if child else 'adult')
        st['map'] = here
        st['age_switchable'] = child is not None and cat.other_age_map(here, not child) is not None
        bags = []
        for key, label, size_h, _name_h, _prefix, sizes in cat.BAGS:
            now, may = self.bag_sizes(key)
            choices = ([now] if now not in sizes else []) + may
            bags.append({'key': key, 'label': label, 'now': now,
                         'choices': [{'n': n, 'text': 'None' if n == 0 else f'{cat.SIZES[sizes.index(n)] if n in sizes else "?"} ({n})'}
                                     for n in choices]})
        st['bags'] = bags
        st['amounts'] = [{'item': item, 'label': label, 'n': self.val(cat.stock(item)), 'most': self.limit(item)}
                         for label, item, _bag, _most in cat.AMOUNTS]
        bottles = []
        for have, _use, what in cat.BOTTLES:
            if not self.val(have):
                bottles.append(0)
            else:
                c = self.val(what)
                bottles.append(next((i + 1 for i, (h, _l) in enumerate(cat.BOTTLE_CONTENTS) if h == c), 0))
        st['bottle_choices'] = ['No bottle'] + [label for _h, label in cat.BOTTLE_CONTENTS]
        st['bottles'] = bottles
        st['keys'] = [{'label': label, 'n': self.val(entry), 'most': most} for label, entry, most in cat.SMALL_KEYS]
        st['edited'] = self.slot.edited()
        return st

    @staticmethod
    def number(text, whole=True):
        text = str(text).strip()
        try:
            x = float(text)
        except ValueError:
            raise ValueError(f'"{text}" is not a number.' if text else 'Type a number.') from None
        if whole and x != int(x):
            raise ValueError(f'{text}: a whole number is needed.')
        return int(x) if whole else x

    def r_set_stat(self, q):
        """key and value as the Stats view sends them: max_hearts, hearts, meter (index), magic, wallet (index), rupees,
        bag:<key> (size), n:<item> (count), bottle:<i> (choice index), key:<i> (count)"""
        self.need_slot()
        key, value = q['key'], q['value']
        if key == 'max_hearts':
            n = self.number(value)
            if not 3 <= n <= 20:
                raise ValueError('Heart containers: 3 to 20.')
            self.write_vital('max_hearts', n * 4)
            if (self.val('PlayerStatus.Life') or 0) > n * 4:
                self.write_vital('hearts', n * 4)
        elif key == 'hearts':
            x = self.number(value, whole=False)
            top = (self.val('PlayerStatus.MaxLife') or 0) / 4
            if x * 4 != int(x * 4) or not 0 <= x <= top:
                raise ValueError(f'Hearts now: 0 to {top:g}, in quarter hearts (like 2.75).')
            self.write_vital('hearts', int(x * 4))
        elif key == 'meter':
            most, _label, gifts = cat.MAGIC_METERS[int(value)]
            self.write_vital('max_magic', most * 10)
            for m in cat.MAGIC_METERS:            # the Great Fairy gifts that give the meter go with it
                for gift in m[2]:
                    self.put(cat.stock(gift), 1 if gift in gifts else 0)
            if (self.val('PlayerStatus.MP') or 0) > most * 10:
                self.write_vital('magic', most * 10)
        elif key == 'magic':
            x = self.number(value, whole=False)
            top = (self.val('PlayerStatus.MPMax') or 0) / 10
            if round(x * 10) != x * 10 or not 0 <= x <= top:
                raise ValueError(f'Magic now: 0 to {top:g}.')
            self.write_vital('magic', round(x * 10))
        elif key == 'wallet':
            item, _label, most = cat.WALLETS[int(value)]
            self.put(cat.WALLET_NAME, item)
            self.put(cat.RUPEE_LIMIT, most)
            for w in cat.WALLETS:
                self.put(cat.stock(w[0]), 1 if w[0] == item else 0)
            if (self.val(cat.RUPEES) or 0) > most:
                self.put(cat.RUPEES, most)
                self.put(cat.CAPTION_RUPEES, most, 'caption')
        elif key == 'rupees':
            n = self.number(value)
            most = self.val(cat.RUPEE_LIMIT) or 0
            if not 0 <= n <= most:
                raise ValueError(f'Rupees: 0 to {most} (the wallet\'s size).')
            self.put(cat.RUPEES, n)
            self.put(cat.CAPTION_RUPEES, n, 'caption')
        elif key.startswith('bag:'):
            _k, _label, size_h, name_h, prefix, sizes = next(b for b in cat.BAGS if b[0] == key[4:])
            n = self.number(value)
            if n in sizes:
                tier = sizes.index(n)
                self.put(size_h, n)
                for t in range(tier + 1):            # the smaller bags were found on the way
                    self.put(cat.stock(f'{prefix}_{cat.SIZES[t]}'), 1)
                if name_h:
                    self.put(name_h, f'{prefix}_{cat.SIZES[tier]}')
        elif key.startswith('n:'):
            item = key[2:]
            n = self.number(value)
            top = max(self.limit(item), self.val(cat.stock(item)) or 0)
            if not 0 <= n <= top:
                label = next(a[0] for a in cat.AMOUNTS if a[1] == item)
                bagged = any(a[1] == item and a[2] for a in cat.AMOUNTS)
                raise ValueError(f'{label}: 0 to {top}' + (' (a bigger bag holds more).' if bagged else '.'))
            self.put(cat.stock(item), n)
        elif key.startswith('bottle:'):
            have, use, what = cat.BOTTLES[int(key[7:])]
            choice = int(value)
            if choice == 0:
                self.put(have, 0)
                self.put(use, False)
                self.put(what, cat.BOTTLE_CONTENTS[0][0])
            else:
                self.put(have, 1)
                self.put(use, True)
                self.put(what, cat.BOTTLE_CONTENTS[choice - 1][0])
        elif key.startswith('key:'):
            label, entry, most = cat.SMALL_KEYS[int(key[4:])]
            n = self.number(value)
            if not 0 <= n <= most:
                raise ValueError(f'{label} keys: 0 to {most}.')
            self.put(entry, n)
        else:
            raise ValueError('unknown setting ' + key)
        return self.r_stats(q)

    def r_fill(self, q):
        """what: hearts, magic, rupees (to the most), amounts (every count to its bag), keys (every small key)"""
        self.need_slot()
        what = q['what']
        if what == 'hearts':
            self.write_vital('hearts', self.val('PlayerStatus.MaxLife') or 0)
        elif what == 'magic':
            self.write_vital('magic', self.val('PlayerStatus.MPMax') or 0)
        elif what == 'rupees':
            most = self.val(cat.RUPEE_LIMIT) or 0
            self.put(cat.RUPEES, most)
            self.put(cat.CAPTION_RUPEES, most, 'caption')
        elif what == 'amounts':
            for _label, item, _bag, _most in cat.AMOUNTS:
                if item == 'Obj_Heart_Piece':      # (four make a heart container: three is the most)
                    continue
                top = self.limit(item)
                if top and (self.val(cat.stock(item)) or 0) < top:
                    self.put(cat.stock(item), top)
        elif what == 'keys':
            for _label, entry, most in cat.SMALL_KEYS:
                self.put(entry, most)
        return self.r_stats(q)

    def r_age(self, q):
        """Young to adult or back: the map Link is saved on goes to the other age's version of it (that is what the game
        goes by), with 'is a child' and the file-select screen's map to match. Only outdoors, where each area has a map for
        each age; in a dungeon both ages share one map. Held items stay: each age keeps what it had."""
        self.need_slot()
        if self.val(cat.IS_CHILD) is None:
            raise ValueError('This save does not say Link\'s age.')
        to_child = not self.val(cat.IS_CHILD)
        here = self.val(cat.CURRENT_MAP)
        there = cat.other_age_map(here, to_child)
        if there is None:
            raise ValueError(f'Link is saved in {here or "a place"}, which has one map for both ages (a dungeon or a '
                             'house), so his age cannot be changed here. In the game, go outside (Kakariko, Hyrule Field, '
                             'Kokiri Forest, the Market...), save there, then switch.')
        self.put(cat.CURRENT_MAP, there)
        caption = self.val(cat.CAPTION_MAP, 'caption')
        if caption:
            self.put(cat.CAPTION_MAP, caption.replace(here, there), 'caption')
        self.put(cat.IS_CHILD, to_child)
        return self.r_stats(q)

    # -- inventory
    def item_state(self, item):
        e = self.slot.get(cat.stock(item))
        if e is None:
            return None, False
        flags = [self.slot.get(f) for f in cat.got_flags(item)]
        return e.value, e.changed or any(f is not None and f.changed for f in flags)

    def r_items(self, q):
        self.need_slot()
        rows = []
        for item, label, grp, age, givable in cat.ITEMS:
            n, changed = self.item_state(item)
            if n is None:
                continue
            rows.append({'item': item, 'label': label, 'group': grp, 'age': age, 'givable': givable, 'n': n,
                         'have': ('Yes' if n == 1 else str(n)) if givable and n else str(n) if n else 'No',
                         'changed': changed})
        return {'items': rows, 'groups': list(cat.GROUPS), 'edited': self.slot.edited()}

    def give(self, item):
        if not self.slot.get(cat.stock(item)):
            return False
        if (self.val(cat.stock(item)) or 0) < 1:
            self.put(cat.stock(item), 1)
        for f in cat.got_flags(item):
            self.put(f, True)
        return True

    def take(self, item, forget):
        label = next(x[1] for x in cat.ITEMS if x[0] == item)
        if item in cat.DEFAULT_CLOTHES:
            return f'{label}: the default clothes stay.'
        for slot_entry in cat.EQUIPPED:
            if self.val(slot_entry) == item:
                return f'{label} is equipped: equip something else in the game first.'
        self.put(cat.stock(item), 0)
        if forget:
            for f in cat.got_flags(item):
                self.put(f, False)
        return ''

    def r_give(self, q):
        """items: ids; give: true (have it, and found) or false (take it away; forget: also not found)"""
        self.need_slot()
        problems, done = [], 0
        for item in q['items']:
            label, givable = next((x[1], x[4]) for x in cat.ITEMS if x[0] == item)
            if not givable:
                problems.append(f'{label}: set it in the Stats view (sizes and counts).')
                continue
            if q['give']:
                done += self.give(item)
            else:
                why = self.take(item, q.get('forget', False))
                if why:
                    problems.append(why)
                else:
                    done += 1
        return {**self.r_items(q), 'problems': problems, 'done': done}

    def r_give_all(self, q):
        self.need_slot()
        missing = [x for x in cat.ITEMS if x[4] and self.slot.get(cat.stock(x[0])) and not self.val(cat.stock(x[0]))]
        for x in missing:
            self.give(x[0])
        return {**self.r_items(q), 'done': len(missing)}

    # -- progress flags and every entry
    def r_flags(self, q):
        self.need_slot()
        sf = self.slot.files['progress']
        words = (q.get('search') or '').lower().split()
        group, show = q.get('group') or 'All', q.get('show') or 'All'
        rows, total = [], 0
        for i, e in enumerate(sf.entries):
            if e.type != 'Bool':
                continue
            name = self.names.names.get(e.hash)
            if not name:
                continue
            total += 1
            g = cat.flag_group(name)
            if group != 'All' and g != group:
                continue
            if show == 'On' and not e.value or show == 'Off' and e.value or show == 'Edited' and not e.changed:
                continue
            if words and not all(w in name.lower() for w in words):
                continue
            rows.append({'i': i, 'name': name, 'group': g, 'on': bool(e.value), 'changed': e.changed})
        rows.sort(key=lambda r: r['name'].lower())
        return {'flags': rows[:MAX_ROWS], 'shown': len(rows), 'total': total, 'groups': list(cat.FLAG_GROUPS),
                'named': bool(self.names.names), 'edited': self.slot.edited()}

    def r_set_flags(self, q):
        """indices into progress.sav's entries; to: true, false, or null to flip each"""
        self.need_slot()
        sf = self.slot.files['progress']
        for i in q['indices']:
            e = sf.entries[int(i)]
            if e.type == 'Bool':
                sf.set(e, (not e.value) if q.get('to') is None else bool(q['to']))
        return self.r_flags(q)

    def entry_name(self, h):
        return self.names.names.get(h) or cat.EXTRA_NAMES.get(h) or f'#{h:08x}'

    def r_entries(self, q):
        self.need_slot()
        kind = q.get('kind') or 'progress'
        sf = self.slot.files.get(kind)
        if not sf:
            return {'entries': [], 'shown': 0, 'kinds': list(self.slot.files), 'edited': self.slot.edited()}
        words = (q.get('search') or '').lower().split()
        edited_only = q.get('show') == 'Edited'
        rows = []
        for i, e in enumerate(sf.entries):
            name = self.entry_name(e.hash)
            if edited_only and not e.changed:
                continue
            text = fmt(self.names, e)
            if words and not all(w in f'{name} {e.type} {text}'.lower() for w in words):
                continue
            rows.append({'i': i, 'name': name, 'type': e.type, 'value': text, 'changed': e.changed,
                         'editable': e.editable and e.value is not None and not e.is_list})
        rows.sort(key=lambda r: (r['name'].startswith('#'), r['name'].lower()))
        return {'entries': rows[:MAX_ROWS], 'shown': len(rows), 'kinds': list(self.slot.files), 'edited': self.slot.edited()}

    def r_set_entry(self, q):
        self.need_slot()
        kind = q.get('kind') or 'progress'
        sf = self.slot.files[kind]
        e = sf.entries[int(q['i'])]
        if not e.editable or e.is_list or e.value is None:
            raise ValueError('This entry cannot be edited here.')
        sf.set(e, parse_item(self.names, e, e.base, q['text']))
        return self.r_entries(q)

    # -- writing
    def r_save(self, q):
        self.need_slot()
        backups = self.game / 'save-backups'
        stamp = time.strftime('%Y-%m-%d %H%M%S')
        n = 0
        for sf in self.slot.files.values():
            if sf.dirty:
                dst = backups / stamp / sf.path.parent.name / sf.path.name
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(sf.path.read_bytes())
                sf.save()
                n += 1
        return {'written': n, 'backup': str(backups / stamp) if n else '', 'edited': 0}

    def r_revert(self, q):
        self.need_slot()
        self.slot = Slot(self.slot.paths)
        return {'edited': 0}


def send(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + '\n')
    sys.stdout.flush()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--game', required=True)
    p.add_argument('--user')
    a = p.parse_args()
    try:
        sys.stdin.reconfigure(encoding='utf-8')
        sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        pass
    ed = Editor(a.game, a.user)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            q = json.loads(line)
            fn = getattr(ed, 'r_' + q.get('cmd', ''), None)
            if fn is None:
                raise ValueError('unknown request ' + str(q.get('cmd')))
            send({'ok': True, **fn(q)})
        except (ValueError, KeyError, IndexError, OSError, RuntimeError) as err:
            send({'ok': False, 'error': str(err)})
        if os.environ.get('HOOKSHOT_SAVEEDIT_ONE'):
            break


if __name__ == '__main__':
    main()
