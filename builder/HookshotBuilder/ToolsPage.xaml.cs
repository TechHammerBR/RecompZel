using System.Diagnostics;
using System.IO;
using System.Text.Json.Nodes;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;

namespace HookshotBuilder;

/// Mods + Editor (beside Play on the ready page and the launcher): the game folder's mods, on or off and in order
/// (ModList.cs, hookshot_mods.txt as the Insert menu's Mods tab keeps it), and the save editor (SaveEditorClient.cs and
/// nx2/saveedit/server.py): Link's hearts, magic, rupees, age, bags, counts, bottles and keys; the items; the story flags;
/// every entry of the slot's files. Nothing is written until Save (the saves after a backup, in save-backups in the game
/// folder), and nothing while the game runs.
partial class ToolsPage : UserControl
{
    Tools? tools;
    string game = "";
    ModList? mods;
    bool modsDirty;
    SaveEditorClient? client;
    bool saveReady, filling;
    int edited;
    public Action? Back;
    public Action<string>? Play;
    public Action<string>? Rebuild;   // (MainWindow: the folder built again, as Update builds it, then its mix kept: PatchBuilds)

    public ToolsPage()
    {
        InitializeComponent();
        foreach (var s in new[] { "All", "Have", "Missing", "Edited" }) InvShow.Items.Add(s);
        foreach (var s in new[] { "All", "On", "Off", "Edited" }) FlagShow.Items.Add(s);
        InvShow.SelectedIndex = FlagShow.SelectedIndex = 0;
    }

    /// The page for a game folder: its mods now, the save editor when its tab is opened
    public void Open(Tools? t, string folder)
    {
        tools = t;
        if (!string.Equals(game, folder, StringComparison.OrdinalIgnoreCase))
        {
            Close();
            game = folder;
        }
        mods = new ModList(game);
        modsDirty = false;
        FillMods();
        Watch();
        ModsTab.IsChecked = true;
        Show(ModsView);
        SetStatus("");
    }

    /// The backend let go (the page left, or another game folder)
    public void Close()
    {
        StopWatching();
        client?.Dispose();
        client = null;
        saveReady = false;
        edited = 0;
        SlotPick.Items.Clear();
    }

    void Show(FrameworkElement view)
    {
        ModsView.Visibility = view == ModsView ? Visibility.Visible : Visibility.Collapsed;
        SaveView.Visibility = view == SaveView ? Visibility.Visible : Visibility.Collapsed;
    }

    void SetStatus(string text, bool bad = false)
    {
        Status.Text = text;
        Status.Foreground = (Brush)FindResource(bad ? "Bad" : "InkSoft");
    }

    static bool GameRunning(string folder)
    {
        foreach (var p in Process.GetProcessesByName("hookshot"))
        {
            try
            {
                var exe = p.MainModule?.FileName;
                if (exe == null || string.Equals(Path.GetDirectoryName(exe), folder.TrimEnd('\\'), StringComparison.OrdinalIgnoreCase)) return true;
            }
            catch (Exception) { return true; }   // (not readable: as if it were this one)
        }
        return false;
    }

    // ================================================================ the head and the foot
    void BackClick(object sender, RoutedEventArgs e)
    {
        if (Unsaved() && MessageBox.Show(Window.GetWindow(this), "Leave without saving your changes?", "Hookshot",
                                         MessageBoxButton.YesNo, MessageBoxImage.Question) != MessageBoxResult.Yes)
            return;
        Close();
        Back?.Invoke();
    }

    bool Unsaved() => modsDirty || edited > 0;

    async void TopTabChanged(object sender, RoutedEventArgs e)
    {
        if (!IsLoaded && sender == ModsTab) return;
        if (sender == ModsTab) { Show(ModsView); return; }
        Show(SaveView);
        if (!saveReady) await StartSaves();
    }

    async Task<bool> SaveAll()
    {
        if (GameRunning(game))
        {
            SetStatus("Close the game first: a running game writes over its saves and reads its mods only when it starts.", true);
            return false;
        }
        var said = new List<string>();
        try
        {
            if (modsDirty && mods != null)
            {
                mods.Save();
                modsDirty = false;
                said.Add("mods saved");
            }
            if (client != null && edited > 0)
            {
                var r = await client.Ask(SaveEditorClient.Req("save"));
                edited = 0;
                said.Add($"save written ({r["written"]} files; the old ones are in save-backups)");
                await RefreshSaveView();
            }
        }
        catch (Exception ex)
        {
            SetStatus("Not saved: " + ex.Message, true);
            return false;
        }
        SetStatus(said.Count > 0 ? char.ToUpper(said[0][0]) + string.Join(", ", said)[1..] + "." : "Nothing to save.");
        return true;
    }

    async void SaveClick(object sender, RoutedEventArgs e) => await SaveAll();

    async void SavePlayClick(object sender, RoutedEventArgs e)
    {
        if (!await SaveAll()) return;
        Close();
        Play?.Invoke(game);
    }

    async void RevertClick(object sender, RoutedEventArgs e)
    {
        if (mods != null && modsDirty)
        {
            mods.Reload();
            modsDirty = false;
            FillMods();
        }
        if (client != null && edited > 0)
        {
            try
            {
                await client.Ask(SaveEditorClient.Req("revert"));
                edited = 0;
                await RefreshSaveView();
            }
            catch (Exception ex) { SetStatus(ex.Message, true); return; }
        }
        SetStatus("Changes undone.");
    }

    // ================================================================ Mods
    // ---- the mods' code patches: the mix ticked against the one the game was built with (PatchBuilds.cs)
    string patchWant = "none";
    void RefreshPatchBar()
    {
        if (mods == null) return;
        patchWant = PatchBuilds.KeyOf(mods.PatchLines());
        var built = PatchBuilds.KeyBuilt(game);
        if (!mods.AnyPatches && built == "none" || patchWant == built)
            PatchBar.Visibility = Visibility.Collapsed;
        else
        {
            var before = PatchBuilds.Has(game, patchWant);
            PatchText.Text = "The code patches ticked are not the ones this game was built with. " +
                             (before ? "It was built with this mix before: Apply switches to it in a few seconds."
                                     : "Rebuild to use them (as long as an update: the code is translated again). Until then the game plays as it was built.");
            PatchButton.Content = before ? "Apply" : "Rebuild";
            PatchBar.Visibility = Visibility.Visible;
        }
        var kept = PatchBuilds.Size(game);
        KeptRow.Visibility = kept > 0 ? Visibility.Visible : Visibility.Collapsed;
        KeptText.Text = $"Builds kept for other mixes of code patches: {Finder.Size(kept)}";
    }

    async void PatchClick(object sender, RoutedEventArgs e)
    {
        if (mods == null) return;
        if (GameRunning(game)) { SetStatus("Close the game first.", true); return; }
        PatchButton.IsEnabled = false;
        try
        {
            mods.Save();   // (the build reads the ticks from hookshot_mods.txt)
            modsDirty = false;
            var want = patchWant;
            SetStatus("Keeping this build for its mix of patches…");
            await Task.Run(() => PatchBuilds.Store(game));   // (the mix in the folder now: switching back to it is a copy too)
            if (await Task.Run(() => PatchBuilds.Restore(game, want)))
            {
                SetStatus("Switched to the build with these code patches.");
                RefreshPatchBar();
                return;
            }
            Close();
            Rebuild?.Invoke(game);
        }
        catch (Exception ex) { SetStatus("Not switched: " + ex.Message, true); }
        finally { PatchButton.IsEnabled = true; }
    }

    void FreeKeptClick(object sender, RoutedEventArgs e)
    {
        try { PatchBuilds.Clear(game); } catch (Exception ex) { SetStatus("Not freed: " + ex.Message, true); }
        RefreshPatchBar();
    }

    // ---- the mods folder watched while the page is open: a mod copied in, taken out or changed shows at once (Refresh keeps
    // the switches and order made here). Changes come in bursts (a copy is many files): read once they settle, 600 ms
    FileSystemWatcher? folderWatch, modsWatch;
    System.Windows.Threading.DispatcherTimer? settle;

    void Changed() => Dispatcher.BeginInvoke(() => { settle?.Stop(); settle?.Start(); });

    void Watch()
    {
        StopWatching();
        settle = new System.Windows.Threading.DispatcherTimer { Interval = TimeSpan.FromMilliseconds(600) };
        settle.Tick += (_, _) => { settle?.Stop(); ReloadMods(auto: true); };
        try
        {
            // (the game folder itself, not its subfolders: a mods folder made, removed or renamed, then the mods folder watched)
            folderWatch = new FileSystemWatcher(game) { NotifyFilter = NotifyFilters.DirectoryName, IncludeSubdirectories = false };
            folderWatch.Created += (_, e) => { if (IsModsFolder(e.FullPath)) { Dispatcher.BeginInvoke(WatchMods); Changed(); } };
            folderWatch.Deleted += (_, e) => { if (IsModsFolder(e.FullPath)) Changed(); };
            folderWatch.Renamed += (_, e) => { if (IsModsFolder(e.FullPath) || IsModsFolder(e.OldFullPath)) { Dispatcher.BeginInvoke(WatchMods); Changed(); } };
            folderWatch.EnableRaisingEvents = true;
        }
        catch (Exception) { folderWatch = null; }
        WatchMods();
    }

    void WatchMods()
    {
        modsWatch?.Dispose();
        modsWatch = null;
        if (mods == null || !Directory.Exists(mods.Root)) return;
        try
        {
            modsWatch = new FileSystemWatcher(mods.Root)
            {
                IncludeSubdirectories = true,
                NotifyFilter = NotifyFilters.DirectoryName | NotifyFilters.FileName | NotifyFilters.LastWrite | NotifyFilters.Size,
            };
            modsWatch.Created += (_, _) => Changed();
            modsWatch.Deleted += (_, _) => Changed();
            modsWatch.Changed += (_, _) => Changed();
            modsWatch.Renamed += (_, _) => Changed();
            modsWatch.Error += (_, _) => Dispatcher.BeginInvoke(() => { WatchMods(); Changed(); });   // (too many changes at once)
            modsWatch.EnableRaisingEvents = true;
        }
        catch (Exception) { modsWatch = null; }
    }

    bool IsModsFolder(string path) =>
        mods != null && string.Equals(Path.TrimEndingDirectorySeparator(path), Path.TrimEndingDirectorySeparator(mods.Root), StringComparison.OrdinalIgnoreCase);

    void StopWatching()
    {
        settle?.Stop();
        settle = null;
        folderWatch?.Dispose();
        modsWatch?.Dispose();
        folderWatch = modsWatch = null;
    }

    void ReloadMods(bool auto)
    {
        if (mods == null) return;
        var names = mods.Mods.Select(m => m.Name).ToHashSet();
        mods.Refresh();
        var added = mods.Mods.Where(m => !names.Contains(m.Name)).Select(m => m.Name.Split('/').Last()).ToList();
        var gone = names.Count - (mods.Mods.Count - added.Count);
        FillMods();
        if (added.Count > 0) SetStatus("New in the mods folder: " + string.Join(", ", added) + ". It's ticked: Save to keep it.");
        else if (gone > 0) SetStatus($"{gone} mod{(gone == 1 ? "" : "s")} gone from the mods folder.");
        else if (!auto) SetStatus("The mods folder read again.");
    }

    async void ReloadClick(object sender, RoutedEventArgs e)
    {
        if (ModsView.Visibility == Visibility.Visible) { ReloadMods(auto: false); return; }
        if (client == null || !saveReady) return;
        if (edited > 0 && MessageBox.Show(Window.GetWindow(this), "Read the saves again and drop the changes not saved yet?", "Hookshot",
                                          MessageBoxButton.YesNo, MessageBoxImage.Question) != MessageBoxResult.Yes)
            return;
        var keep = SlotPick.SelectedItem is ComboBoxItem { Tag: ValueTuple<string, string> t } ? t : default;
        client.Dispose();
        client = null;
        saveReady = false;
        edited = 0;
        await StartSaves();   // (the slots listed again, a save made since among them; then the slot that was open)
        foreach (ComboBoxItem item in SlotPick.Items)
            if (item.Tag is ValueTuple<string, string> t2 && t2 == keep && SlotPick.SelectedItem != item) { SlotPick.SelectedItem = item; break; }
        SetStatus("The saves read again.");
    }

    void FillMods()
    {
        RefreshPatchBar();
        ModRows.Children.Clear();
        if (mods == null) return;
        if (mods.Mods.Count == 0)
        {
            ModRows.Children.Add(new TextBlock
            {
                Text = $"No mods in {mods.Root}. Add mods… copies a mod folder in (one with a romfs, exefs or cheats folder inside it), " +
                       "or a folder of them.",
                Style = (Style)FindResource("Note"), Margin = new Thickness(12),
            });
            return;
        }
        for (var i = 0; i < mods.Mods.Count; i++)
        {
            var m = mods.Mods[i];
            var index = i;
            if (i > 0) ModRows.Children.Add(new Border { Height = 1, Background = (Brush)FindResource("GlassLine"), Margin = new Thickness(8, 0, 8, 0) });
            var tick = new CheckBox { Style = (Style)FindResource("Tick"), IsChecked = m.On, VerticalAlignment = VerticalAlignment.Center };
            tick.Click += (_, _) => { m.On = tick.IsChecked == true; mods.Clashes(); modsDirty = true; FillMods(); };
            var parts = new List<string>();
            if (m.RomFs) parts.Add($"{m.Files} game file{(m.Files == 1 ? "" : "s")}");
            if (m.ExeFs) parts.Add("code patches (applied when the game is built)");
            if (m.Cheats) parts.Add("cheats");
            var slash = m.Name.LastIndexOf('/');   // (a mod deeper in, as emulators keep them: its own name, and where it is)
            if (slash >= 0) parts.Add("in " + m.Name[..slash]);
            var name = new TextBlock { Text = m.Name[(slash + 1)..], FontWeight = FontWeights.SemiBold, TextTrimming = TextTrimming.CharacterEllipsis };
            var detail = new TextBlock { Text = string.Join(" · ", parts), Style = (Style)FindResource("Faint") };
            var texts = new StackPanel { Children = { name, detail } };
            if (m.On && m.LosesTo.Count > 0)
                texts.Children.Add(new TextBlock
                {
                    Text = "Some of its files are replaced by " + string.Join(", ", m.LosesTo) + " (lower in the list)",
                    FontSize = 12, Foreground = (Brush)FindResource("Warn"), TextWrapping = TextWrapping.Wrap,
                });
            var up = new Button { Style = (Style)FindResource("Small"), Content = "▲", Width = 38, Visibility = i > 0 ? Visibility.Visible : Visibility.Hidden, ToolTip = "Up (its files lose to more mods)" };
            var down = new Button { Style = (Style)FindResource("Small"), Content = "▼", Width = 38, Margin = new Thickness(6, 0, 0, 0),
                                    Visibility = i < mods.Mods.Count - 1 ? Visibility.Visible : Visibility.Hidden, ToolTip = "Down (its files win over the mods above)" };
            up.Click += (_, _) => { mods.Move(index, -1); modsDirty = true; FillMods(); };
            down.Click += (_, _) => { mods.Move(index, 1); modsDirty = true; FillMods(); };
            var row = new Grid { Margin = new Thickness(10, 8, 10, 8) };
            row.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
            row.ColumnDefinitions.Add(new ColumnDefinition());
            row.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
            var buttons = new StackPanel { Orientation = Orientation.Horizontal, Children = { up, down }, VerticalAlignment = VerticalAlignment.Center };
            Grid.SetColumn(texts, 1);
            Grid.SetColumn(buttons, 2);
            texts.Margin = new Thickness(4, 0, 12, 0);
            row.Children.Add(tick);
            row.Children.Add(texts);
            row.Children.Add(buttons);
            ModRows.Children.Add(row);
        }
    }

    void AddModsClick(object sender, RoutedEventArgs e)
    {
        if (mods == null) return;
        var pick = new Microsoft.Win32.OpenFolderDialog { Title = "A mod folder, or a folder of mods" };
        if (pick.ShowDialog(Window.GetWindow(this)) != true) return;
        try
        {
            var (added, there) = mods.Add(pick.FolderName);
            var keep = mods.Mods.ToDictionary(m => m.Name, m => m.On);
            mods.Reload();
            modsDirty = modsDirty || added.Count > 0;
            FillMods();
            SetStatus(added.Count == 0 && there.Count == 0
                ? "No mod in that folder: a mod has a romfs, exefs or cheats folder inside it."
                : (added.Count > 0 ? "Added " + string.Join(", ", added) + ". " : "") +
                  (there.Count > 0 ? "Already there (left as they are): " + string.Join(", ", there) + "." : ""),
                added.Count == 0 && there.Count == 0);
        }
        catch (Exception ex) { SetStatus("Not copied: " + ex.Message, true); }
    }

    void OpenModsClick(object sender, RoutedEventArgs e)
    {
        if (mods == null) return;
        Directory.CreateDirectory(mods.Root);
        Process.Start(new ProcessStartInfo("explorer.exe", $"\"{mods.Root}\"") { UseShellExecute = true });
    }

    // ================================================================ the save editor
    async Task StartSaves()
    {
        if (tools == null) { Wait("The build tools are not on this PC, and the save editor needs their Python."); return; }
        Wait("Starting the save editor…");
        var user = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "Hookshot");
        client = SaveEditorClient.Start(tools, game, Directory.Exists(user) ? user : null, out var error);
        if (client == null) { Wait(error ?? "The save editor could not start."); return; }
        client.Progress = text => Dispatcher.BeginInvoke(() => Wait(text + "\n(once for this game: the names of the save's entries, from your game files)"));
        try
        {
            var acc = await client.Ask(SaveEditorClient.Req("accounts"));
            SlotPick.Items.Clear();
            foreach (var a in acc["accounts"]!.AsArray())
                foreach (var s in a!["slots"]!.AsArray())
                {
                    var bits = new List<string> { s!["label"]!.GetValue<string>() };
                    if (s["where"] is { } w) bits.Add(w.GetValue<string>());
                    if (s["hearts"] is { } h) bits.Add(h.GetValue<string>() + " hearts");
                    if (s["saved"] is { } t) bits.Add("saved " + t.GetValue<string>());
                    SlotPick.Items.Add(new ComboBoxItem
                    {
                        Content = string.Join("  ·  ", bits),
                        Tag = (a["path"]!.GetValue<string>(), s["slot"]!.GetValue<string>()),
                    });
                }
            if (SlotPick.Items.Count == 0)
            {
                Wait("No saves yet: play the game once and save, then come back.");
                return;
            }
            await client.Ask(SaveEditorClient.Req("names"));
            saveReady = true;
            filling = true;
            SlotPick.SelectedIndex = 0;
            filling = false;
            await OpenSlot();
        }
        catch (Exception ex) { Wait("The save editor stopped: " + ex.Message); }
    }

    void Wait(string text)
    {
        SaveWait.Text = text;
        SaveWait.Visibility = Visibility.Visible;
        StatsView.Visibility = InvView.Visibility = FlagView.Visibility = EntryView.Visibility = Visibility.Collapsed;
    }

    async void SlotPicked(object sender, SelectionChangedEventArgs e)
    {
        if (filling || !saveReady || client == null) return;
        if (edited > 0 && MessageBox.Show(Window.GetWindow(this), "Open another slot without saving the changes to this one?", "Hookshot",
                                          MessageBoxButton.YesNo, MessageBoxImage.Question) != MessageBoxResult.Yes)
        {
            filling = true;
            SlotPick.SelectedItem = e.RemovedItems.Count > 0 ? e.RemovedItems[0] : null;
            filling = false;
            return;
        }
        await OpenSlot();
    }

    async Task OpenSlot()
    {
        if (client == null || SlotPick.SelectedItem is not ComboBoxItem { Tag: ValueTuple<string, string> tag }) return;
        try
        {
            await client.Ask(SaveEditorClient.Req("open", ("account", tag.Item1), ("slot", tag.Item2)));
            edited = 0;
            SaveWait.Visibility = Visibility.Collapsed;
            await RefreshSaveView();
        }
        catch (Exception ex) { Wait(ex.Message); }
    }

    async void SaveTabChanged(object sender, RoutedEventArgs e)
    {
        if (saveReady) await RefreshSaveView();
    }

    async Task RefreshSaveView()
    {
        if (client == null || !saveReady) return;
        StatsView.Visibility = StatsTab.IsChecked == true ? Visibility.Visible : Visibility.Collapsed;
        InvView.Visibility = InvTab.IsChecked == true ? Visibility.Visible : Visibility.Collapsed;
        FlagView.Visibility = FlagTab.IsChecked == true ? Visibility.Visible : Visibility.Collapsed;
        EntryView.Visibility = EntryTab.IsChecked == true ? Visibility.Visible : Visibility.Collapsed;
        try
        {
            if (StatsTab.IsChecked == true) FillStats(await client.Ask(SaveEditorClient.Req("stats")));
            else if (InvTab.IsChecked == true) FillItems(await client.Ask(SaveEditorClient.Req("items")));
            else if (FlagTab.IsChecked == true) FillFlags(await AskFlags("flags"));
            else FillEntries(await AskEntries("entries"));
        }
        catch (Exception ex) { SetStatus(ex.Message, true); }
    }

    void Edited(JsonObject r)
    {
        if (r["edited"] is { } n) edited = n.GetValue<int>();
        if (edited > 0) SetStatus($"{edited} change{(edited == 1 ? "" : "s")} not saved yet: Save writes them (with the game closed).");
    }

    // ---- Stats
    void FillStats(JsonObject st)
    {
        Edited(st);
        StatCards.Children.Clear();
        double? num(string k) => st[k] is JsonValue v && v.TryGetValue<double>(out var d) ? d : null;
        string text(double? d) => d is { } x ? x.ToString("0.##", System.Globalization.CultureInfo.InvariantCulture) : "";

        var life = Card("Health and magic");
        Line(life, "Hearts", Box(text(num("hearts")), v => SetStat("hearts", v)), $"of {text(num("max_hearts"))} (the containers)", ("Fill", () => Fill("hearts")));
        Line(life, "Heart containers", Box(text(num("max_hearts")), v => SetStat("max_hearts", v)), "3 to 20");
        Line(life, "Magic meter", Pick(st["meters"]!.AsArray(), st["meter"]!.GetValue<int>(), i => SetStat("meter", i.ToString())));
        Line(life, "Magic", Box(text(num("magic")), v => SetStat("magic", v)), $"of {text(num("max_magic"))}", ("Fill", () => Fill("magic")));

        var money = Card("Rupees and Link");
        Line(money, "Wallet", Pick(st["wallets"]!.AsArray(), st["wallet"]!.GetValue<int>(), i => SetStat("wallet", i.ToString())));
        Line(money, "Rupees", Box(st["rupees"]?.ToString() ?? "", v => SetStat("rupees", v)), $"of {st["rupee_limit"]}", ("Fill", () => Fill("rupees")));
        var age = st["age"]?.GetValue<string>();
        var where = st["map"]?.GetValue<string>() ?? "";
        var switchable = st["age_switchable"]?.GetValue<bool>() == true;
        Line(money, "Age", new TextBlock
             {
                 Text = age == null ? "?" : age == "young" ? "Young Link" : "Adult Link", VerticalAlignment = VerticalAlignment.Center,
                 ToolTip = "Saved on " + where + (switchable ? "" : ": a place with one map for both ages (a dungeon or a house), so the age stays"),
             },
             switchable ? null : "in a dungeon", switchable ? (age == "young" ? "Make adult" : "Make young", () => Age()) : null);

        var bags = Card("Bags and quiver");
        foreach (var b in st["bags"]!.AsArray())
        {
            var key = b!["key"]!.GetValue<string>();
            var choices = b["choices"]!.AsArray();
            var now = b["now"]!.GetValue<int>();
            var at = choices.Select((c, i) => (c, i)).First(x => x.c!["n"]!.GetValue<int>() == now).i;
            Line(bags, b["label"]!.GetValue<string>(), Pick(new JsonArray(choices.Select(c => (JsonNode?)JsonValue.Create(c!["text"]!.GetValue<string>())).ToArray()), at,
                                                          i => SetStat("bag:" + key, choices[i]!["n"]!.ToString())));
        }

        var counts = Card("Counts", ("Fill all", () => Fill("amounts")));
        foreach (var a in st["amounts"]!.AsArray())
        {
            if (a!["n"] == null) continue;
            var item = a["item"]!.GetValue<string>();
            var most = a["most"]!.GetValue<int>();
            Line(counts, a["label"]!.GetValue<string>(), Box(a["n"]!.ToString(), v => SetStat("n:" + item, v)), most > 0 ? $"of {most}" : "no bag yet");
        }

        var bottles = Card("Bottles");
        var bottleChoices = st["bottle_choices"]!.AsArray();
        var bi = 0;
        foreach (var b in st["bottles"]!.AsArray())
        {
            var i = bi++;
            Line(bottles, $"Bottle {"ABCDE"[i]}", Pick(bottleChoices, b!.GetValue<int>(), c => SetStat($"bottle:{i}", c.ToString())));
        }

        var keys = Card("Small keys", ("Fill all", () => Fill("keys")));
        var ki = 0;
        foreach (var k in st["keys"]!.AsArray())
        {
            var i = ki++;
            if (k!["n"] == null) continue;
            Line(keys, k["label"]!.GetValue<string>(), Box(k["n"]!.ToString(), v => SetStat($"key:{i}", v)), $"of {k["most"]}");
        }
    }

    StackPanel Card(string title, (string Text, Action Do)? action = null)
    {
        var body = new StackPanel();
        var head = new Grid { Margin = new Thickness(0, 0, 0, 8) };
        head.Children.Add(new TextBlock { Text = title.ToUpperInvariant(), Style = (Style)FindResource("Label"), Margin = new Thickness(0, 4, 0, 0) });
        if (action is { } a)
        {
            var b = new Button { Style = (Style)FindResource("LinkButton"), Content = a.Text, HorizontalAlignment = HorizontalAlignment.Right };
            b.Click += (_, _) => a.Do();
            head.Children.Add(b);
        }
        body.Children.Add(head);
        StatCards.Children.Add(new Border { Style = (Style)FindResource("Card"), Padding = new Thickness(16, 12, 16, 14), Margin = new Thickness(0, 0, 10, 10), Width = 397, Child = body });
        return body;
    }

    void Line(StackPanel card, string label, FrameworkElement control, string? note = null, (string Text, Action Do)? action = null)
    {
        var row = new Grid { Margin = new Thickness(0, 3, 0, 3) };
        row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(140) });
        row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(control is TextBox ? 90 : control is TextBlock ? 110 : 220) });
        row.ColumnDefinitions.Add(new ColumnDefinition());
        row.Children.Add(new TextBlock { Text = label, FontSize = 13, VerticalAlignment = VerticalAlignment.Center, TextTrimming = TextTrimming.CharacterEllipsis });
        Grid.SetColumn(control, 1);
        row.Children.Add(control);
        var tail = new StackPanel { Orientation = Orientation.Horizontal, VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(10, 0, 0, 0) };
        if (!string.IsNullOrEmpty(note)) tail.Children.Add(new TextBlock { Text = note, Style = (Style)FindResource("Faint"), VerticalAlignment = VerticalAlignment.Center, TextTrimming = TextTrimming.CharacterEllipsis });
        if (action is { } a)
        {
            var b = new Button { Style = (Style)FindResource("LinkButton"), Content = a.Text, Margin = new Thickness(10, 0, 0, 0), VerticalAlignment = VerticalAlignment.Center };
            b.Click += (_, _) => a.Do();
            tail.Children.Add(b);
        }
        Grid.SetColumn(tail, 2);
        row.Children.Add(tail);
        card.Children.Add(row);
    }

    TextBox Box(string value, Action<string> set)
    {
        var box = new TextBox { Style = (Style)FindResource("Field"), Text = value };
        var was = value;
        void commit() { if (box.Text != was) { was = box.Text; set(box.Text); } }
        box.LostKeyboardFocus += (_, _) => commit();
        box.KeyDown += (_, e) => { if (e.Key == Key.Enter) commit(); };
        return box;
    }

    ComboBox Pick(JsonArray choices, int at, Action<int> set)
    {
        var pick = new ComboBox { Style = (Style)FindResource("SmallChoice") };
        foreach (var c in choices) pick.Items.Add(c!.GetValue<string>());
        pick.SelectedIndex = at;
        pick.SelectionChanged += (_, _) => { if (pick.SelectedIndex >= 0 && pick.SelectedIndex != at) set(pick.SelectedIndex); };
        return pick;
    }

    async void SetStat(string key, string value) => await StatAsk(SaveEditorClient.Req("set_stat", ("key", key), ("value", value)));
    async void Fill(string what) => await StatAsk(SaveEditorClient.Req("fill", ("what", what)));
    async void Age() => await StatAsk(SaveEditorClient.Req("age"));

    async Task StatAsk(JsonObject q)
    {
        if (client == null) return;
        try { FillStats(await client.Ask(q)); }
        catch (Exception ex)
        {
            SetStatus(ex.Message, true);
            try { FillStats(await client.Ask(SaveEditorClient.Req("stats"))); } catch (Exception) { }
        }
    }

    // ---- Inventory
    sealed record ItemRow(string Id, string Label, string Group, string Age, string Have, bool Givable, bool Changed, int N)
    {
        public FontWeight Weight => Changed ? FontWeights.Bold : FontWeights.Normal;
        public Brush HaveBrush => (Brush)Application.Current.FindResource(N > 0 ? "Go" : "InkFaint");
    }
    List<ItemRow> items = new();

    void FillItems(JsonObject r)
    {
        Edited(r);
        items = r["items"]!.AsArray().Select(x => new ItemRow(x!["item"]!.GetValue<string>(), x["label"]!.GetValue<string>(), x["group"]!.GetValue<string>(),
            x["age"]!.GetValue<string>(), x["have"]!.GetValue<string>(), x["givable"]!.GetValue<bool>(), x["changed"]!.GetValue<bool>(), x["n"]!.GetValue<int>())).ToList();
        if (InvGroup.Items.Count == 0)
        {
            InvGroup.Items.Add("All");
            foreach (var g in r["groups"]!.AsArray()) InvGroup.Items.Add(g!.GetValue<string>());
            InvGroup.SelectedIndex = 0;
        }
        InvFilter();
    }

    void InvFilter()
    {
        var words = InvSearch.Text.ToLowerInvariant().Split(' ', StringSplitOptions.RemoveEmptyEntries);
        var group = InvGroup.SelectedItem as string ?? "All";
        var show = InvShow.SelectedItem as string ?? "All";
        var keep = InvList.SelectedItems.Cast<ItemRow>().Select(x => x.Id).ToHashSet();
        var rows = items.Where(x => (group == "All" || x.Group == group) &&
                                    (show == "All" || show == "Have" && x.N > 0 || show == "Missing" && x.N == 0 || show == "Edited" && x.Changed) &&
                                    words.All(w => $"{x.Label} {x.Id} {x.Group}".ToLowerInvariant().Contains(w))).ToList();
        InvList.ItemsSource = rows;
        foreach (var x in rows.Where(x => keep.Contains(x.Id))) InvList.SelectedItems.Add(x);
    }

    void InvFilterChanged(object sender, RoutedEventArgs e)
    {
        InvHint.Visibility = InvSearch.Text.Length == 0 ? Visibility.Visible : Visibility.Collapsed;
        if (IsLoaded) InvFilter();
    }

    async Task Give(bool give, IEnumerable<string> ids)
    {
        if (client == null) return;
        var list = new JsonArray(ids.Select(i => (JsonNode?)JsonValue.Create(i)).ToArray());
        if (list.Count == 0) { SetStatus("Pick an item in the list first (Ctrl or Shift for several)."); return; }
        try
        {
            var r = await client.Ask(SaveEditorClient.Req("give", ("items", list), ("give", give), ("forget", ForgetTick.IsChecked == true)));
            FillItems(r);
            var problems = r["problems"]!.AsArray().Select(p => p!.GetValue<string>()).ToList();
            if (problems.Count > 0) SetStatus(string.Join(" ", problems), true);
        }
        catch (Exception ex) { SetStatus(ex.Message, true); }
    }

    async void GiveClick(object sender, RoutedEventArgs e) => await Give(true, InvList.SelectedItems.Cast<ItemRow>().Select(x => x.Id));
    async void TakeClick(object sender, RoutedEventArgs e) => await Give(false, InvList.SelectedItems.Cast<ItemRow>().Select(x => x.Id));

    async void InvToggle(object sender, MouseButtonEventArgs e)
    {
        if (InvList.SelectedItem is ItemRow x) await Give(x.N == 0, new[] { x.Id });
    }

    async void GiveAllClick(object sender, RoutedEventArgs e)
    {
        if (client == null) return;
        if (MessageBox.Show(Window.GetWindow(this), "Give every item this slot is missing? Quest items (medallions, stones) can change what the story does next.",
                            "Hookshot", MessageBoxButton.YesNo, MessageBoxImage.Question) != MessageBoxResult.Yes)
            return;
        try { FillItems(await client.Ask(SaveEditorClient.Req("give_all"))); }
        catch (Exception ex) { SetStatus(ex.Message, true); }
    }

    // ---- Progress (the story flags)
    sealed record FlagRow(int I, string Name, string Group, bool On, bool Changed)
    {
        public string Value => On ? "On" : "Off";
        public FontWeight Weight => Changed ? FontWeights.Bold : FontWeights.Normal;
        public Brush ValueBrush => (Brush)Application.Current.FindResource(On ? "Go" : "InkFaint");
    }

    Task<JsonObject> AskFlags(string cmd, params (string, JsonNode?)[] more) =>
        client!.Ask(SaveEditorClient.Req(cmd, more.Concat(new (string, JsonNode?)[]
        {
            ("search", FlagSearch.Text), ("group", FlagGroup.SelectedItem as string ?? "All"), ("show", FlagShow.SelectedItem as string ?? "All"),
        }).ToArray()));

    void FillFlags(JsonObject r)
    {
        Edited(r);
        if (FlagGroup.Items.Count == 0)
        {
            filling = true;
            FlagGroup.Items.Add("All");
            foreach (var g in r["groups"]!.AsArray()) FlagGroup.Items.Add(g!.GetValue<string>());
            FlagGroup.SelectedIndex = 0;
            filling = false;
        }
        var keep = FlagList.SelectedItems.Cast<FlagRow>().Select(x => x.I).ToHashSet();
        var rows = r["flags"]!.AsArray().Select(x => new FlagRow(x!["i"]!.GetValue<int>(), x["name"]!.GetValue<string>(), x["group"]!.GetValue<string>(),
                                                               x["on"]!.GetValue<bool>(), x["changed"]!.GetValue<bool>())).ToList();
        FlagList.ItemsSource = rows;
        foreach (var x in rows.Where(x => keep.Contains(x.I))) FlagList.SelectedItems.Add(x);
        var shown = r["shown"]!.GetValue<int>();
        FlagCount.Text = r["named"]!.GetValue<bool>()
            ? $"{shown} of {r["total"]} flags" + (shown > rows.Count ? $" (the first {rows.Count}: search to narrow it)" : "")
            : "No flag names: the game files were not found in the game folder.";
    }

    CancellationTokenSource? flagSoon;
    async void FlagFilterChanged(object sender, RoutedEventArgs e)
    {
        FlagHint.Visibility = FlagSearch.Text.Length == 0 ? Visibility.Visible : Visibility.Collapsed;
        if (!IsLoaded || filling || client == null || !saveReady) return;
        flagSoon?.Cancel();
        var me = flagSoon = new CancellationTokenSource();
        try { await Task.Delay(200, me.Token); } catch (TaskCanceledException) { return; }
        try { FillFlags(await AskFlags("flags")); } catch (Exception ex) { SetStatus(ex.Message, true); }
    }

    async Task SetFlags(bool? to)
    {
        var picked = FlagList.SelectedItems.Cast<FlagRow>().Select(x => (JsonNode?)JsonValue.Create(x.I)).ToArray();
        if (picked.Length == 0) { SetStatus("Pick a flag in the list first (Ctrl or Shift for several)."); return; }
        try { FillFlags(await AskFlags("set_flags", ("indices", new JsonArray(picked)), ("to", to is { } b ? JsonValue.Create(b) : null))); }
        catch (Exception ex) { SetStatus(ex.Message, true); }
    }

    async void FlagOnClick(object sender, RoutedEventArgs e) => await SetFlags(true);
    async void FlagOffClick(object sender, RoutedEventArgs e) => await SetFlags(false);
    async void FlagFlip(object sender, MouseButtonEventArgs e) => await SetFlags(null);

    // ---- All entries
    sealed record EntryRowData(int I, string Name, string Type, string Value, bool Changed, bool Editable)
    {
        public FontWeight Weight => Changed ? FontWeights.Bold : FontWeights.Normal;
    }

    static readonly (string Kind, string Label)[] Kinds =
        { ("progress", "Progress (progress.sav)"), ("caption", "File select (caption.sav)"), ("option", "Options (option.sav)"), ("account", "Account (account.sav)") };

    string EntryKindNow => EntryKind.SelectedItem is ComboBoxItem { Tag: string k } ? k : "progress";

    Task<JsonObject> AskEntries(string cmd, params (string, JsonNode?)[] more) =>
        client!.Ask(SaveEditorClient.Req(cmd, more.Concat(new (string, JsonNode?)[]
        {
            ("kind", EntryKindNow), ("search", EntrySearch.Text), ("show", EntryEdited.IsChecked == true ? "Edited" : "All"),
        }).ToArray()));

    void FillEntries(JsonObject r)
    {
        Edited(r);
        var kinds = r["kinds"]!.AsArray().Select(k => k!.GetValue<string>()).ToHashSet();
        if (EntryKind.Items.Count == 0)
        {
            filling = true;
            foreach (var (k, label) in Kinds.Where(x => kinds.Contains(x.Kind))) EntryKind.Items.Add(new ComboBoxItem { Content = label, Tag = k });
            EntryKind.SelectedIndex = 0;
            filling = false;
        }
        var keep = (EntryList.SelectedItem as EntryRowData)?.I;
        var rows = r["entries"]!.AsArray().Select(x => new EntryRowData(x!["i"]!.GetValue<int>(), x["name"]!.GetValue<string>(), x["type"]!.GetValue<string>(),
                                                                     x["value"]!.GetValue<string>(), x["changed"]!.GetValue<bool>(), x["editable"]!.GetValue<bool>())).ToList();
        EntryList.ItemsSource = rows;
        EntryList.SelectedItem = rows.FirstOrDefault(x => x.I == keep);
    }

    CancellationTokenSource? entrySoon;
    async void EntryFilterChanged(object sender, RoutedEventArgs e)
    {
        EntryHint.Visibility = EntrySearch.Text.Length == 0 ? Visibility.Visible : Visibility.Collapsed;
        if (!IsLoaded || filling || client == null || !saveReady) return;
        entrySoon?.Cancel();
        var me = entrySoon = new CancellationTokenSource();
        try { await Task.Delay(200, me.Token); } catch (TaskCanceledException) { return; }
        try { FillEntries(await AskEntries("entries")); } catch (Exception ex) { SetStatus(ex.Message, true); }
    }

    void EntryPicked(object sender, SelectionChangedEventArgs e)
    {
        var row = EntryList.SelectedItem as EntryRowData;
        EntryValue.IsEnabled = EntrySet.IsEnabled = row?.Editable == true;
        EntryValue.Text = row?.Editable == true ? row.Value : row?.Value ?? "";
    }

    async Task SetEntry()
    {
        if (client == null || EntryList.SelectedItem is not EntryRowData row || !row.Editable) return;
        try { FillEntries(await AskEntries("set_entry", ("i", row.I), ("text", EntryValue.Text))); }
        catch (Exception ex) { SetStatus(ex.Message, true); }
    }

    async void EntrySetClick(object sender, RoutedEventArgs e) => await SetEntry();
    async void EntryValueKey(object sender, KeyEventArgs e) { if (e.Key == Key.Enter) await SetEntry(); }
}
