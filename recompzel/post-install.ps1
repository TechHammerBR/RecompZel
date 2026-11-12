# post-install.ps1 - roda depois da instalacao: deixa o jogo facil de abrir.
# Cria: atalho "Zelda OoT (RecompZel)" (abre o jogo) e, se houver launcher, "RecompZel Launcher" na area de trabalho, entrada no menu Iniciar e "Jogar RecompZel.bat" dentro da pasta do jogo.
# Nao apaga nada. Pode rodar quantas vezes quiser (ex.: se mover a pasta do jogo).
# Uso: powershell -ExecutionPolicy Bypass -File .\post-install.ps1 [-GameDir D:\PSN nativo\ZELDA OCT\RecompZel-main\Jogo]
param([string]$GameDir)
$ErrorActionPreference = 'Continue'

if (-not $GameDir) {
    foreach ($d in 'D:\PSN nativo\ZELDA OCT\RecompZel-main\Jogo', (Join-Path $env:USERPROFILE 'Games\RecompZel'), 'C:\Games\HookshotDev') {
        if (Test-Path -LiteralPath (Join-Path $d 'RecompZel.exe')) { $GameDir = $d; break }
    }
}
$exe = if ($GameDir) { Join-Path $GameDir 'RecompZel.exe' } else { '' }
if (-not $exe -or -not (Test-Path -LiteralPath $exe)) { Write-Host 'Nao achei o RecompZel.exe. Informe a pasta: .\post-install.ps1 -GameDir "D:\PSN nativo\ZELDA OCT\RecompZel-main\Jogo"'; exit 1 }

# icone: o do proprio executavel
$Sh = New-Object -ComObject WScript.Shell
function Novo-Atalho($caminho) {
    $a = $Sh.CreateShortcut($caminho)
    $a.TargetPath = $exe
    $a.WorkingDirectory = $GameDir
    $a.IconLocation = "$exe,0"
    $a.Description = 'Zelda Ocarina of Time recompilado (RecompZel)'
    $a.Save()
}

$desktop = [Environment]::GetFolderPath('Desktop')
Novo-Atalho (Join-Path $desktop 'Zelda OoT (RecompZel).lnk')
$menu = Join-Path ([Environment]::GetFolderPath('Programs')) 'RecompZel'
New-Item -ItemType Directory -Force -Path $menu | Out-Null
Novo-Atalho (Join-Path $menu 'Zelda OoT (RecompZel).lnk')

# Launcher (menu com Jogar, progresso e opcoes), se esta maquina tem o launcher.ps1 em D:\PSN nativo\ZELDA OCT\RecompZel-main\DEV
$launcher = 'D:\PSN nativo\ZELDA OCT\RecompZel-main\DEV\launcher.ps1'
if (Test-Path -LiteralPath $launcher) {
    $b = $Sh.CreateShortcut((Join-Path $desktop 'RecompZel Launcher.lnk'))
    $b.TargetPath = "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe"
    $b.Arguments = "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$launcher`""
    $b.WorkingDirectory = 'D:\PSN nativo\ZELDA OCT\RecompZel-main\DEV'
    $b.IconLocation = "$exe,0"
    $b.Description = 'Launcher do RecompZel'
    $b.Save()
}

# "Jogar RecompZel.bat": um clique na propria pasta do jogo, funciona mesmo se o atalho for apagado
$bat = Join-Path $GameDir 'Jogar RecompZel.bat'
@('@echo off', 'cd /d "%~dp0"', 'start "" "%~dp0RecompZel.exe"') | Set-Content -LiteralPath $bat -Encoding ASCII

Write-Host "Pronto. Para jogar, use o atalho 'Zelda OoT (RecompZel)' na area de trabalho."
Write-Host "Tambem: $bat"
