# criar-atalhos.ps1 - cria atalhos na area de trabalho (nao apaga nada)
# Uso: powershell -ExecutionPolicy Bypass -File C:\DEV\criar-atalhos.ps1

$Desktop = [Environment]::GetFolderPath('Desktop')
$GameDir = 'C:\Games\HookshotDev'
$GameExe = Join-Path $GameDir 'hookshot.exe'
$Launcher = 'C:\DEV\launcher.ps1'
$Sh = New-Object -ComObject WScript.Shell

if (-not (Test-Path $GameExe)) { Write-Host "Nao achei $GameExe"; exit 1 }

# 1) Atalho direto para jogar
$a = $Sh.CreateShortcut((Join-Path $Desktop 'Zelda OoT (RecompZel).lnk'))
$a.TargetPath = $GameExe
$a.WorkingDirectory = $GameDir
$a.IconLocation = "$GameExe,0"
$a.Description = 'Zelda Ocarina of Time recompilado (RecompZel)'
$a.Save()

# 2) Atalho para o launcher com progresso e opcoes
if (Test-Path $Launcher) {
    $b = $Sh.CreateShortcut((Join-Path $Desktop 'RecompZel Launcher.lnk'))
    $b.TargetPath = "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe"
    $b.Arguments = "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Launcher`""
    $b.WorkingDirectory = 'C:\DEV'
    $b.IconLocation = "$GameExe,0"
    $b.Description = 'Launcher do RecompZel'
    $b.Save()
}

Write-Host "Atalhos criados em: $Desktop"
Get-ChildItem $Desktop -Filter '*.lnk' | Where-Object { $_.Name -like 'Zelda OoT*' -or $_.Name -like 'RecompZel*' } | ForEach-Object { Write-Host (' - ' + $_.Name) }
