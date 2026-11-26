using System.IO;
using System.Security.Cryptography;
using System.Text;

namespace HookshotBuilder;

/// The game as built for each mix of the mods' code patches (ExeFS patches: nx2/exefs_patches.py applies them when the game is
/// built, so a mod with code patches switched on or off needs a build). After a build its game files that the patches change
/// (the game's exe, image.bin and exefs_patches.txt, the list of patches it was built with) are kept in cache/patch-builds/<mix>
/// in the game folder, so going back to a mix built before is a copy of those files, not a build. An entry is used only by the
/// build it came from (hookshot_version.txt the same): another version's game files are never mixed in. The newest Keep are kept.
static class PatchBuilds
{
    public const int Keep = 4;
    const string Stamp = "stamp.txt", List = "files.txt";

    static string Root(string game) => Path.Combine(game, "cache", "patch-builds");

    /// The game's exe as Play starts it (MainWindow.GameExe): bin\hookshot.exe beside the launcher, or the folder's own
    public static string GameExe(string game)
    {
        var bin = Path.Combine(game, "bin", "hookshot.exe");
        var top = Path.Combine(game, "hookshot.exe");
        if (!File.Exists(bin)) return top;
        // (a development build puts the game in the folder itself: a bin\hookshot.exe left by an earlier packaged build is
        // older than it, and the folder's hookshot.exe is then the game, not the small launcher)
        if (File.Exists(top) && new FileInfo(top).Length > 64L << 20 && File.GetLastWriteTimeUtc(top) > File.GetLastWriteTimeUtc(bin))
            return top;
        return bin;
    }

    static string Version(string game)
    {
        try { return File.ReadAllText(Path.Combine(game, "hookshot_version.txt")).Trim(); } catch (Exception) { return ""; }
    }

    /// A mix's name: the patch files (mod, file, FNV-1a of its bytes) sorted, hashed; "none" without any
    public static string KeyOf(IEnumerable<string> lines)
    {
        var sorted = lines.Where(l => l.Length > 0).OrderBy(l => l, StringComparer.Ordinal).ToList();
        if (sorted.Count == 0) return "none";
        return Convert.ToHexString(SHA1.HashData(Encoding.UTF8.GetBytes(string.Join("\n", sorted))))[..16].ToLowerInvariant();
    }

    /// The mix the game in the folder was built with: exefs_patches.txt's files (make_game.py writes it; none: no patches)
    public static string KeyBuilt(string game)
    {
        var path = Path.Combine(game, "exefs_patches.txt");
        if (!File.Exists(path)) return "none";
        return KeyOf(File.ReadAllLines(path).Where(l => !l.StartsWith('#'))
                         .Select(l => l.Split('\t')).Where(f => f.Length >= 3).Select(f => $"{f[0]}\t{f[1]}\t{f[2]}"));
    }

    static string[] Files(string game)
    {
        var exe = Path.GetRelativePath(game, GameExe(game));
        var files = new List<string> { exe, "image.bin" };
        if (File.Exists(Path.Combine(game, "exefs_patches.txt"))) files.Add("exefs_patches.txt");
        return files.ToArray();
    }

    public static bool Has(string game, string key)
    {
        var dir = Path.Combine(Root(game), key);
        try { return File.Exists(Path.Combine(dir, List)) && File.ReadAllText(Path.Combine(dir, Stamp)).Trim() == Version(game); }
        catch (Exception) { return false; }
    }

    /// The game in the folder kept as its mix's entry (again when it is there: the newest build of that mix wins)
    public static void Store(string game)
    {
        var files = Files(game);
        if (!files.All(f => File.Exists(Path.Combine(game, f)))) return;   // (no built game here)
        var root = Root(game);
        var key = KeyBuilt(game);
        var dir = Path.Combine(root, key);
        var tmp = dir + ".new";
        if (Directory.Exists(tmp)) Directory.Delete(tmp, true);
        Directory.CreateDirectory(tmp);
        foreach (var f in files)
        {
            var dst = Path.Combine(tmp, f);
            Directory.CreateDirectory(Path.GetDirectoryName(dst)!);
            File.Copy(Path.Combine(game, f), dst);
        }
        File.WriteAllText(Path.Combine(tmp, Stamp), Version(game));
        File.WriteAllLines(Path.Combine(tmp, List), files);   // (last: an entry without its list is a half-written one)
        if (Directory.Exists(dir)) Directory.Delete(dir, true);
        Directory.Move(tmp, dir);
        Prune(game);
    }

    /// The folder's game switched to a mix built before, by this version: true when done
    public static bool Restore(string game, string key)
    {
        if (!Has(game, key)) return false;
        var dir = Path.Combine(Root(game), key);
        var files = File.ReadAllLines(Path.Combine(dir, List));
        foreach (var f in files)
        {
            var dst = Path.Combine(game, f);
            var tmp = dst + ".new";
            File.Copy(Path.Combine(dir, f), tmp, true);
            File.Move(tmp, dst, true);
        }
        if (!files.Contains("exefs_patches.txt")) File.Delete(Path.Combine(game, "exefs_patches.txt"));   // (a mix with no patches)
        Directory.SetLastWriteTimeUtc(dir, DateTime.UtcNow);
        return true;
    }

    static void Prune(string game)
    {
        var root = Root(game);
        foreach (var old in Directory.EnumerateDirectories(root).Select(d => new DirectoryInfo(d))
                                     .OrderByDescending(d => d.LastWriteTimeUtc).Skip(Keep))
            try { old.Delete(true); } catch (Exception) { }
    }

    public static long Size(string game)
    {
        var root = Root(game);
        if (!Directory.Exists(root)) return 0;
        return new DirectoryInfo(root).EnumerateFiles("*", SearchOption.AllDirectories).Sum(f => f.Length);
    }

    public static void Clear(string game)
    {
        var root = Root(game);
        if (Directory.Exists(root)) Directory.Delete(root, true);
    }
}
