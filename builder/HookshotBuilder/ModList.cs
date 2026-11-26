using System.IO;

namespace HookshotBuilder;

/// The game folder's mods as the game sees them (host/mods.c): in "mods" beside the game, any folder up to four deep that
/// holds a romfs, exefs or cheats folder is a mod (as emulators keep them); folders whose names start with '-' or '_' are
/// left out. Their order and switches are hookshot_mods.txt in the game folder, the same file the Insert menu's Mods tab
/// writes: "on <name>" / "off <name>" a line, top first, and "cheat <key> on|off" lines kept as they are. A mod the file does
/// not name goes after the named ones, by name, and is on. When two mods have the same file, the one lower in the list wins.
sealed class ModList
{
    public sealed class Mod
    {
        public required string Name { get; init; }    // (its folder under mods, with / between levels)
        public required string Path { get; init; }
        public bool RomFs, ExeFs, Cheats;
        public bool On = true;
        public int Files;                               // (RomFS files)
        public List<string> LosesTo = new();             // (mods lower in the list with a file this one has: they win it)
    }

    public string GameFolder { get; }
    public string Root => System.IO.Path.Combine(GameFolder, "mods");
    string StatePath => System.IO.Path.Combine(GameFolder, "hookshot_mods.txt");
    public List<Mod> Mods { get; } = new();
    readonly List<string> cheatLines = new();
    readonly Dictionary<string, HashSet<string>> files = new(StringComparer.OrdinalIgnoreCase);

    public ModList(string gameFolder)
    {
        GameFolder = gameFolder;
        Reload();
    }

    /// The mods read again from the folder, keeping the switches and order made on the page and not saved yet: those mods in
    /// that order and state, a new one where the saved file (or its name) puts it, a gone one left out
    public void Refresh()
    {
        var before = Mods.Select(m => (m.Name, m.On)).ToList();
        Reload();
        var at = Mods.ToDictionary(m => m.Name);
        var kept = new List<Mod>();
        foreach (var (name, on) in before)
            if (at.Remove(name, out var m)) { m.On = on; kept.Add(m); }
        // (a new mod: after the one before it in the saved order, else first)
        foreach (var m in Mods.Where(m => at.ContainsKey(m.Name)).ToList())
        {
            var i = Mods.IndexOf(m);
            var prev = i > 0 ? kept.FindIndex(k => k.Name == Mods[i - 1].Name) : -1;
            kept.Insert(prev + 1, m);
        }
        Mods.Clear();
        Mods.AddRange(kept);
        Clashes();
    }

    public void Reload()
    {
        Mods.Clear();
        cheatLines.Clear();
        files.Clear();
        if (Directory.Exists(Root)) Find(Root, "", 0);
        Mods.Sort((a, b) => string.Compare(a.Name, b.Name, StringComparison.OrdinalIgnoreCase));
        ReadState();
        foreach (var m in Mods) files[m.Name] = RomFsFiles(m);
        foreach (var m in Mods) m.Files = files[m.Name].Count;
        Clashes();
    }

    void Find(string dir, string name, int depth)
    {
        bool has(string sub) => Directory.Exists(System.IO.Path.Combine(dir, sub));
        if (depth > 0 && (has("romfs") || has("exefs") || has("cheats")))
        {
            Mods.Add(new Mod { Name = name, Path = dir, RomFs = has("romfs"), ExeFs = has("exefs"), Cheats = has("cheats") });
            return;
        }
        if (depth >= 4) return;
        IEnumerable<string> subs;
        try { subs = Directory.EnumerateDirectories(dir); } catch (Exception) { return; }
        foreach (var sub in subs)
        {
            var leaf = System.IO.Path.GetFileName(sub);
            if (leaf.StartsWith('.') || leaf.StartsWith('-') || leaf.StartsWith('_')) continue;
            Find(sub, name.Length > 0 ? name + "/" + leaf : leaf, depth + 1);
        }
    }

    static HashSet<string> RomFsFiles(Mod m)
    {
        var set = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var romfs = System.IO.Path.Combine(m.Path, "romfs");
        if (!Directory.Exists(romfs)) return set;
        try
        {
            foreach (var f in Directory.EnumerateFiles(romfs, "*", SearchOption.AllDirectories))
                set.Add(System.IO.Path.GetRelativePath(romfs, f).Replace('\\', '/'));
        }
        catch (Exception) { }
        return set;
    }

    void ReadState()
    {
        if (!File.Exists(StatePath)) return;
        var placed = 0;
        foreach (var raw in File.ReadAllLines(StatePath))
        {
            var line = raw.TrimEnd('\r');
            var on = line.StartsWith("on ");
            if (on || line.StartsWith("off "))
            {
                var name = line[(on ? 3 : 4)..];
                var i = Mods.FindIndex(placed, m => m.Name == name);
                if (i < 0) continue;
                var m = Mods[i];
                Mods.RemoveAt(i);
                m.On = on;
                Mods.Insert(placed++, m);
            }
            else if (line.StartsWith("cheat ")) cheatLines.Add(line);
        }
    }

    /// Which enabled mods lose a file to an enabled mod lower in the list
    public void Clashes()
    {
        foreach (var m in Mods) m.LosesTo.Clear();
        for (var i = 0; i < Mods.Count; i++)
        {
            if (!Mods[i].On) continue;
            for (var j = i + 1; j < Mods.Count; j++)
                if (Mods[j].On && files.TryGetValue(Mods[i].Name, out var a) && files.TryGetValue(Mods[j].Name, out var b) && a.Overlaps(b))
                    Mods[i].LosesTo.Add(Mods[j].Name);
        }
    }

    /// The code patches the ticked mods have (nx2/exefs_patches.py collect): "mod, file, FNV-1a of its bytes" a line, as
    /// exefs_patches.txt lists them, for PatchBuilds.KeyOf
    public List<string> PatchLines()
    {
        var lines = new List<string>();
        foreach (var m in Mods.Where(m => m.On && m.ExeFs))
        {
            IEnumerable<string> names;
            try { names = Directory.EnumerateFiles(System.IO.Path.Combine(m.Path, "exefs")).Select(System.IO.Path.GetFileName).OfType<string>(); }
            catch (Exception) { continue; }
            foreach (var n in names.Where(n => n.EndsWith(".ips", StringComparison.OrdinalIgnoreCase) || n.EndsWith(".pchtxt", StringComparison.OrdinalIgnoreCase))
                                   .OrderBy(n => n, StringComparer.Ordinal))
            {
                uint h = 0x811C9DC5;
                try { foreach (var b in File.ReadAllBytes(System.IO.Path.Combine(m.Path, "exefs", n))) h = (h ^ b) * 0x01000193; }
                catch (Exception) { continue; }
                lines.Add($"{m.Name}\t{n}\t{h:x8}");
            }
        }
        return lines;
    }

    public bool AnyPatches => Mods.Any(m => m.ExeFs);

    public void Move(int i, int by)
    {
        var j = i + by;
        if (i < 0 || j < 0 || i >= Mods.Count || j >= Mods.Count) return;
        (Mods[i], Mods[j]) = (Mods[j], Mods[i]);
        Clashes();
    }

    /// hookshot_mods.txt as the game writes it (host/mods.c write_state), through a temporary file
    public void Save()
    {
        var lines = new List<string>
        {
            "# Hookshot's mods: their order and switches, as the Mods tab sets them (Insert menu). One line a mod, top of the",
            "# list first: \"on <folder>\" or \"off <folder>\". A mod lower in the list wins a file two mods have. Applies at the",
            "# next start.",
        };
        lines.AddRange(Mods.Select(m => (m.On ? "on " : "off ") + m.Name));
        lines.AddRange(cheatLines);
        var tmp = StatePath + ".new";
        File.WriteAllText(tmp, string.Join("\n", lines) + "\n", new System.Text.UTF8Encoding(false));
        File.Move(tmp, StatePath, true);
    }

    /// A folder copied into mods: the folder itself when it is a mod (holds romfs, exefs or cheats), else each mod inside it.
    /// Returns the names copied in, and those already there (left as they are)
    public (List<string> Added, List<string> There) Add(string folder)
    {
        var added = new List<string>();
        var there = new List<string>();
        bool isMod(string d) => new[] { "romfs", "exefs", "cheats" }.Any(s => Directory.Exists(System.IO.Path.Combine(d, s)));
        var sources = isMod(folder) ? new List<string> { folder }
                                    : Directory.EnumerateDirectories(folder).Where(isMod).ToList();
        Directory.CreateDirectory(Root);
        foreach (var src in sources)
        {
            var dst = System.IO.Path.Combine(Root, System.IO.Path.GetFileName(src.TrimEnd('\\', '/')));
            if (Directory.Exists(dst)) { there.Add(System.IO.Path.GetFileName(dst)); continue; }
            CopyTree(src, dst);
            added.Add(System.IO.Path.GetFileName(dst));
        }
        return (added, there);
    }

    static void CopyTree(string src, string dst)
    {
        Directory.CreateDirectory(dst);
        foreach (var f in Directory.EnumerateFiles(src)) File.Copy(f, System.IO.Path.Combine(dst, System.IO.Path.GetFileName(f)));
        foreach (var d in Directory.EnumerateDirectories(src)) CopyTree(d, System.IO.Path.Combine(dst, System.IO.Path.GetFileName(d)));
    }
}
