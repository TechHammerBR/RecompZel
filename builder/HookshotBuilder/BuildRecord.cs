using System.IO;
using System.Text.Json;

namespace HookshotBuilder;

/// How a game folder was built (nx2/make_game.py write_build_record: .hookshot_build.json): the version, the tools and their
/// Python, the work folder, the toolchain's switches and AMD FSR 4. The Mods page's Rebuild builds the folder again with exactly
/// these, for a change of the mods' code patches: the same version, the same work folder (only what the patches change is done
/// again), and nothing downloaded. A folder without a record (built before records were written) uses the installed Builder's
/// tools of its own version when this PC has them, else says why it cannot.
sealed record BuildRecord(string Version, Tools Tools, string? Work, bool Fsr)
{
    const string Name = ".hookshot_build.json";

    /// The game's version as its hookshot_version.txt says ("version=v2.3.2-115-g..."), null when not known
    public static string? GameVersion(string game)
    {
        try
        {
            return File.ReadAllLines(Path.Combine(game, "hookshot_version.txt"))
                       .FirstOrDefault(l => l.StartsWith("version="))?["version=".Length..].Trim();
        }
        catch (Exception) { return null; }
    }

    /// The way to build this folder again, or why there is none
    public static (BuildRecord? Record, string? Why) Find(string game)
    {
        var version = GameVersion(game);
        var path = Path.Combine(game, Name);
        if (File.Exists(path))
        {
            try
            {
                using var doc = JsonDocument.Parse(File.ReadAllText(path));
                var r = doc.RootElement;
                var root = r.GetProperty("tools").GetString() ?? "";
                var python = r.GetProperty("python").GetString() ?? "";
                var recorded = r.GetProperty("version").GetString();
                if (!File.Exists(Path.Combine(root, "nx2", "make_game.py")) || !File.Exists(python))
                    return (null, $"The build tools this game was made with ({root}) are not on this PC any more. Build it once more " +
                                  "with the Hookshot Builder, then Rebuild works from here.");
                if (version != null && recorded != null && recorded != version)
                    return (null, $"This game is {version}, but its record says {recorded}: build it once more with the Hookshot Builder.");
                var env = new Dictionary<string, string>();
                if (r.TryGetProperty("env", out var e))
                    foreach (var p in e.EnumerateObject()) env[p.Name] = p.Value.GetString() ?? "";
                var work = r.TryGetProperty("work", out var w) ? w.GetString() : null;
                var fsr = r.TryGetProperty("fsr", out var f) && f.ValueKind == JsonValueKind.True;
                return (new BuildRecord(recorded ?? version ?? "", new Tools(root, python) { Env = env }, work, fsr), null);
            }
            catch (Exception ex) { return (null, "This game's build record could not be read: " + ex.Message); }
        }
        // (no record: the installed Builder's tools of this very version, where the Builder keeps each version it set up)
        if (version != null)
        {
            var tools = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "HookshotBuilder",
                                     "versions", version, "HookshotBuilder", "tools");
            var py = Path.Combine(tools, "python", "python.exe");
            if (File.Exists(Path.Combine(tools, "nx2", "make_game.py")) && File.Exists(py))
                return (new BuildRecord(version, new Tools(tools, py), null, File.Exists(Path.Combine(game, ".hookshot_fsr"))), null);
        }
        return (null, $"This game ({version ?? "its version not known"}) was built before games kept a record of their build, and its " +
                      "build tools are not on this PC. Build it once more with the Hookshot Builder, then Rebuild works from here.");
    }

    /// Whether these tools apply the mods' code patches at all (nx2/exefs_patches.py came after v2.3.2)
    public bool AppliesPatches => File.Exists(Path.Combine(Tools.Root, "nx2", "exefs_patches.py"));
}
