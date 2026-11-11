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
    const string Dir = @"C:\DEV";

    [STAThread]
    static int Main(string[] args)
    {
        try
        {
            Directory.CreateDirectory(Dir);
            var asm = Assembly.GetExecutingAssembly();
            foreach (var name in asm.GetManifestResourceNames())
            {
                if (!name.StartsWith("rz.", StringComparison.Ordinal)) continue;
                string file = name.Substring(3);
                string dest = Path.Combine(Dir, file);
                // games.json guarda o perfil do usuario (caminhos); so e criado se ainda nao existe.
                if (file.Equals("games.json", StringComparison.OrdinalIgnoreCase) && File.Exists(dest)) continue;
                using (var src = asm.GetManifestResourceStream(name))
                using (var dst = new FileStream(dest, FileMode.Create, FileAccess.Write, FileShare.Read))
                    src.CopyTo(dst);
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
                "\n\nA pasta C:\\DEV precisa poder ser criada e gravada.", "RecompZel",
                MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}
