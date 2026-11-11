// LauncherStub.cs - o RecompZel-Launcher.exe: um executavel pequeno que leva dentro os scripts do launcher
// (launcher.ps1, build-game.ps1, etc., ver .github/workflows/launcher-exe.yml), copia para C:\DEV e abre o launcher.
// O launcher continua sendo o launcher.ps1; o exe so evita que o usuario precise abrir o PowerShell.
// Compilado com o csc.exe do Windows (.NET Framework 4), sem nada para instalar.
using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Windows.Forms;

static class LauncherStub
{
    // Pasta do launcher: C:\DEV se ja e o layout do desenvolvedor (tem games.json la), senao %LOCALAPPDATA%\RecompZel (nao precisa de permissao em C:\).
    static readonly string Dir = File.Exists(@"C:\DEV\games.json") ? @"C:\DEV" : Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "RecompZel");

    static bool SameBytes(byte[] a, byte[] b)
    {
        if (a.Length != b.Length) return false;
        for (int i = 0; i < a.Length; i++) if (a[i] != b[i]) return false;
        return true;
    }

    // Numero do build (rz.build.txt dentro do exe, o numero da execucao do CI): um exe mais velho nao desfaz um launcher que ja foi atualizado
    static int ReadBuild(string text)
    {
        int n;
        return int.TryParse((text ?? "").Trim(), out n) ? n : 0;
    }

    [STAThread]
    static int Main(string[] args)
    {
        try
        {
            Directory.CreateDirectory(Dir);
            var asm = Assembly.GetExecutingAssembly();
            int embedded = 0, installed = 0;
            using (var bs = asm.GetManifestResourceStream("rz.build.txt"))
            {
                if (bs != null) using (var rd = new StreamReader(bs)) embedded = ReadBuild(rd.ReadToEnd());
            }
            string buildFile = Path.Combine(Dir, "build.txt");
            try { if (File.Exists(buildFile)) installed = ReadBuild(File.ReadAllText(buildFile)); } catch (IOException) { }
            bool keepInstalled = embedded > 0 && installed > embedded;   // ja ha scripts mais novos na pasta: nao volta atras
            foreach (var name in asm.GetManifestResourceNames())
            {
                if (keepInstalled) break;
                if (!name.StartsWith("rz.", StringComparison.Ordinal)) continue;
                if (name == "rz.build.txt") continue;
                string file = name.Substring(3);
                string dest = Path.Combine(Dir, file);
                // games.json guarda o perfil do usuario (caminhos); so e criado se ainda nao existe.
                if (file.Equals("games.json", StringComparison.OrdinalIgnoreCase) && File.Exists(dest)) continue;
                byte[] data;
                using (var src = asm.GetManifestResourceStream(name))
                using (var ms = new MemoryStream())
                {
                    src.CopyTo(ms);
                    data = ms.ToArray();
                }
                // ja esta igual: nao mexe (o launcher aberto pode estar usando o arquivo, como o icone)
                try { if (File.Exists(dest) && File.ReadAllBytes(dest).Length == data.Length && SameBytes(File.ReadAllBytes(dest), data)) continue; }
                catch (IOException) { }
                try { File.WriteAllBytes(dest, data); }
                catch (IOException) { if (!File.Exists(dest)) throw; }                // em uso por outro processo: usa o que ja esta la
                catch (UnauthorizedAccessException) { if (!File.Exists(dest)) throw; }
            }
            if (embedded > 0 && !keepInstalled)
            {
                try { File.WriteAllText(buildFile, embedded.ToString()); } catch (IOException) { }
            }
            var psi = new ProcessStartInfo
            {
                FileName = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Windows),
                    @"System32\WindowsPowerShell\v1.0\powershell.exe"),
                Arguments = "-NoProfile -ExecutionPolicy Bypass -STA -WindowStyle Hidden -File \"" + Path.Combine(Dir, "launcher.ps1") + "\"",
                WorkingDirectory = Dir,
                UseShellExecute = false,
                CreateNoWindow = true,
            };
            Process.Start(psi);
            return 0;
        }
        catch (Exception e)
        {
            MessageBox.Show("Nao foi possivel abrir o RecompZel Launcher.\n\n" + e.Message +
                "\n\nA pasta " + Dir + " precisa poder ser criada e gravada.", "RecompZel",
                MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}
