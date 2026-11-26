using System.Diagnostics;
using System.IO;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace HookshotBuilder;

/// The save editor's backend (nx2/saveedit/server.py, with the build tools' Python): one process while the page is open,
/// a JSON request a line and a JSON answer a line; while the entry names are read from the game files the first time, lines
/// {"progress": ...} come first (reported through Progress). Requests run one at a time, off the UI thread.
sealed class SaveEditorClient : IDisposable
{
    readonly Process proc;
    readonly SemaphoreSlim one = new(1, 1);
    public Action<string>? Progress;

    SaveEditorClient(Process p) => proc = p;

    public static SaveEditorClient? Start(Tools tools, string game, string? user, out string? error)
    {
        error = null;
        var script = Path.Combine(tools.Root, "nx2", "saveedit", "server.py");
        if (!File.Exists(script)) { error = "The save editor is not in these build tools (nx2/saveedit/server.py)."; return null; }
        var si = new ProcessStartInfo(tools.Python)
        {
            WorkingDirectory = tools.Root,
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardInput = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            StandardOutputEncoding = new System.Text.UTF8Encoding(false),
            StandardInputEncoding = new System.Text.UTF8Encoding(false),
        };
        si.Environment["PYTHONIOENCODING"] = "utf-8";
        foreach (var a in tools.PythonArgs ?? Array.Empty<string>()) si.ArgumentList.Add(a);
        si.ArgumentList.Add("-I");
        si.ArgumentList.Add(script);
        si.ArgumentList.Add("--game");
        si.ArgumentList.Add(game);
        if (!string.IsNullOrEmpty(user)) { si.ArgumentList.Add("--user"); si.ArgumentList.Add(user); }
        try
        {
            var p = Process.Start(si)!;
            p.ErrorDataReceived += (_, _) => { };   // (drained: a long complaint cannot stall it)
            p.BeginErrorReadLine();
            return new SaveEditorClient(p);
        }
        catch (Exception ex)
        {
            error = tools.OwnPythonMissing ? Tools.OwnPythonMissingText : "The save editor could not start: " + ex.Message;
            return null;
        }
    }

    /// The answer to one request (its "ok" false: an InvalidOperationException with the backend's reason)
    public async Task<JsonObject> Ask(JsonObject request)
    {
        await one.WaitAsync();
        try
        {
            return await Task.Run(() =>
            {
                proc.StandardInput.WriteLine(request.ToJsonString());
                proc.StandardInput.Flush();
                while (true)
                {
                    var line = proc.StandardOutput.ReadLine() ?? throw new InvalidOperationException("The save editor stopped.");
                    if (line.Length == 0) continue;
                    var node = JsonNode.Parse(line)!.AsObject();
                    if (node["progress"] is { } p) { Progress?.Invoke(p.GetValue<string>()); continue; }
                    if (node["ok"]?.GetValue<bool>() != true) throw new InvalidOperationException(node["error"]?.GetValue<string>() ?? "failed");
                    return node;
                }
            });
        }
        finally { one.Release(); }
    }

    public static JsonObject Req(string cmd, params (string Key, JsonNode? Value)[] args)
    {
        var o = new JsonObject { ["cmd"] = cmd };
        foreach (var (k, v) in args) o[k] = v;
        return o;
    }

    public void Dispose()
    {
        try { proc.StandardInput.Close(); if (!proc.WaitForExit(2000)) proc.Kill(); } catch (Exception) { }
        proc.Dispose();
    }
}
