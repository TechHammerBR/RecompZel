using System.Net.Http;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace HookshotBuilder;

/// (hookshot, 2026-11-15) The Version menu: every release on git.notrexed.dev, read from Forgejo's API page by page when the menu
/// is opened, so a release made after this builder is in it too. The owner asked for a chooser that gets "absolutely every
/// release". No WPF here: tests/test_builder_version_menu.py runs it under .NET 8
static class ReleaseList
{
    const string Api = "https://git.notrexed.dev/api/v1/repos/Hookshot/Hookshot/releases";
    public const int PageSize = 50;   // (Forgejo's most a page)
    const int MostPages = 40;         // (2,000 releases: a stop for a server that never gives a short page)
    public const string SetupAsset = "HookshotBuilder.exe", SetupList = "hookshot-setup.txt";
    // (the first release whose setup installs the release it is told to, --tag: builder/setup/setup.c, v2.0.6. An older one's
    // setup installs the newest instead, so it is listed and not chosen)
    public const string FirstInstallable = "v2.0.6";
    // (a version's tag; the builder-parts, linux-parts, rc and nightly releases hold files, not a version of their own)
    static readonly Regex Version = new(@"^v\d+\.\d+\.\d+(?:-rc\.\d+)?$");

    /// One release: its tag, whether it is a pre-release (a release candidate), when it came out, and whether the builder can
    /// install it (its setup and setup list, and a setup that takes --tag): one it cannot is shown, not chosen
    public sealed record Entry(string Tag, bool Prerelease, DateTimeOffset? Published, bool Installable)
    {
        /// What the menu shows: "v2.3.1 · 15 Nov 2026", a release candidate or a release with no download saying so
        public string Label =>
            Tag + (Published is { } p ? " · " + p.ToString("d MMM yyyy", System.Globalization.CultureInfo.InvariantCulture) : "") +
            (Prerelease ? " · release candidate" : "") + (Installable ? "" : " · can't be installed from here");
    }

    /// The menu's releases from the API's pages (JSON arrays): drafts and tags that are no version left out, each tag once,
    /// newest version first (Updater.Newer: a release after its release candidates)
    public static List<Entry> From(IEnumerable<string> pages)
    {
        var seen = new HashSet<string>();
        var list = new List<Entry>();
        foreach (var page in pages)
        {
            using var doc = JsonDocument.Parse(page);
            if (doc.RootElement.ValueKind != JsonValueKind.Array) continue;
            foreach (var r in doc.RootElement.EnumerateArray())
            {
                var tag = r.TryGetProperty("tag_name", out var t) ? t.GetString() : null;
                if (tag == null || !Version.IsMatch(tag) || !seen.Add(tag)) continue;
                if (r.TryGetProperty("draft", out var d) && d.ValueKind == JsonValueKind.True) continue;
                var pre = r.TryGetProperty("prerelease", out var p) && p.ValueKind == JsonValueKind.True;
                DateTimeOffset? when = r.TryGetProperty("published_at", out var w) && w.ValueKind == JsonValueKind.String &&
                                       DateTimeOffset.TryParse(w.GetString(), out var at) ? at : null;
                bool setup = false, setupList = false;
                if (r.TryGetProperty("assets", out var assets) && assets.ValueKind == JsonValueKind.Array)
                    foreach (var a in assets.EnumerateArray())
                        if (a.TryGetProperty("name", out var n))
                        {
                            setup |= n.GetString() == SetupAsset;
                            setupList |= n.GetString() == SetupList;
                        }
                list.Add(new Entry(tag, pre, when, setup && setupList && !Newer(FirstInstallable, tag)));
            }
        }
        list.Sort((a, b) => Newer(a.Tag, b.Tag) ? -1 : Newer(b.Tag, a.Tag) ? 1 : string.CompareOrdinal(a.Tag, b.Tag));
        return list;
    }

    /// Every release, all pages, newest first; null when git.notrexed.dev did not answer (a page that fails part way: null too,
    /// so the menu never shows a list cut short as if it were all)
    public static async Task<List<Entry>?> Fetch(CancellationToken token = default)
    {
        using var http = new HttpClient { Timeout = TimeSpan.FromSeconds(20) };
        http.DefaultRequestHeaders.UserAgent.ParseAdd("HookshotBuilder");
        var pages = new List<string>();
        try
        {
            for (var page = 1; page <= MostPages; page++)
            {
                var text = await http.GetStringAsync($"{Api}?limit={PageSize}&page={page}", token);
                pages.Add(text);
                using var doc = JsonDocument.Parse(text);
                if (doc.RootElement.ValueKind != JsonValueKind.Array || doc.RootElement.GetArrayLength() < PageSize) break;
            }
        }
        catch (Exception) { return null; }
        return From(pages);
    }

    /// a newer than b, vX.Y.Z[-rc.N] in semver order (as Updater.Newer, without its nightlies: no tag here is one)
    public static bool Newer(string a, string b)
    {
        static long[] Key(string v)
        {
            var m = Regex.Match(v, @"^v(\d+)\.(\d+)\.(\d+)(?:-rc\.(\d+))?$");
            return new[] { long.Parse(m.Groups[1].Value), long.Parse(m.Groups[2].Value), long.Parse(m.Groups[3].Value),
                           m.Groups[4].Success ? long.Parse(m.Groups[4].Value) : long.MaxValue };
        }
        var x = Key(a);
        var y = Key(b);
        for (var i = 0; i < x.Length; i++)
            if (x[i] != y[i]) return x[i] > y[i];
        return false;
    }
}
