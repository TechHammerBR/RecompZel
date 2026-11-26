using System.Text.RegularExpressions;

namespace HookshotBuilder;

/// The build's last step, the shaders' preparation (nx2/make_game.py prepare_shaders): the argument that leaves it to the game's
/// first start, and what its row says once the build is done
static class ShaderStep
{
    public const string Id = "shaders";
    public const string Later = "--no-prepare-shaders";
    // (make_game.py NOT_PREPARED: a plain line, so a builder that does not know it only shows it)
    static readonly Regex NotPrepared = new(@"^the shaders were not prepared now \((.*)\): (.*)$");
    const string FirstStart = "the game prepares them at its first start";   // (make_game.py FIRST_START)

    /// make_game's arguments with the player's choice (unticked: the game prepares its shaders at its first start)
    public static List<string> Args(List<string> args, bool prepare)
    {
        if (!prepare) args.Add(Later);
        return args;
    }

    /// What the row says when make_game's line says the shaders were not prepared, else null: left to the first start and why,
    /// or (the GPU driver stopped responding) why and what happens instead
    public static string? Note(string line) => NotPrepared.Match(line) is { Success: true } m
        ? m.Groups[2].Value == FirstStart ? $"Left to the game's first start: {m.Groups[1].Value}"
        : $"Not prepared: {m.Groups[1].Value}. {char.ToUpperInvariant(m.Groups[2].Value[0])}{m.Groups[2].Value[1..]}"
        : null;

    /// The line under the row of a finished build when the shaders were not prepared, or null when they were (a check mark).
    /// began: the game's @@stage shaders came; note: Note of make_game's not-prepared line
    public static string? Skipped(bool began, string? note) => note ?? (began ? null : "Left to the game's first start");

    // (the game's own countdown, every 10 s while it builds pipelines: gpu/vk/vk_draw.cpp prepare_progress_log,
    // "vk: noted pipelines: 18009 of 32713 pipelines in 2447 s, about 1998 s left")
    static readonly Regex PipelinesLeft = new(@"vk: [a-z]+ pipelines: \d+ of \d+ pipelines in \d+ s, about (\d+) s left");

    /// The seconds the game's line says are left, or -1 when the line is not one of its countdowns
    public static double LeftIn(string line) =>
        PipelinesLeft.Match(line) is { Success: true } m && double.TryParse(m.Groups[1].Value, out var s) ? s : -1;

    /// The shaders' time left, in seconds, or -1 while it cannot be told yet. (A slow PC took 58 minutes and more here while the
    /// window said "Usually about 45 minutes" for the whole build: a player took it for stuck.) The game's own countdown while it
    /// is fresh (said: what it said; since: seconds since it said it, under 40), less the time since; else the step's bar so far
    /// (fraction done after elapsed seconds), once it has moved enough to go by
    public static double Left(double said, double since, double fraction, double elapsed)
    {
        if (said >= 0 && since >= 0 && since < 40) return Math.Max(said - since, 0);
        if (fraction > 0.03 && fraction < 1 && elapsed >= 20) return elapsed / fraction * (1 - fraction);
        return -1;
    }
}
