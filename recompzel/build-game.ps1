# Compila o jogo a partir do seu .nup, usando as ferramentas de compilacao do RecompZel/Hookshot Builder.
# Uso:  powershell -ExecutionPolicy Bypass -File .\build-game.ps1 [-Nup <arquivo.nup>] [-Out <pasta do jogo>]
# Sem parametros: procura o .nup em Downloads, Desktop e Documentos e instala em C:\Games\RecompZel (ou %USERPROFILE%\Games\RecompZel).
# Ao terminar com sucesso, cria o atalho na area de trabalho (post-install.ps1).
param([string]$Nup, [string]$Out, [string]$Work, [string]$Log, [switch]$Dlss)
$ErrorActionPreference = 'Continue'
. (Join-Path $PSScriptRoot 'env-recompzel.ps1')
[System.Diagnostics.Process]::GetCurrentProcess().PriorityClass = 'BelowNormal'   # o PC continua utilizavel durante o build

# 1) arquivo do jogo
if (-not $Nup) {
    $dirs = @('Downloads', 'Desktop', 'Documents') | ForEach-Object { Join-Path $env:USERPROFILE $_ } | Where-Object { Test-Path $_ }
    $todos = @(Get-ChildItem -Path $dirs -Recurse -File -Filter '*.nup' -ErrorAction SilentlyContinue | Sort-Object Length -Descending)
    # primeiro o que tem o ID do jogo (0400486024DEC000) no nome; se o arquivo foi renomeado, usa o maior .nup achado
    $Nup = $todos | Where-Object { $_.Name -like '*0400486024DEC000*' } | Select-Object -First 1 -ExpandProperty FullName
    if (-not $Nup -and $todos.Count -gt 0) {
        $Nup = $todos[0].FullName
        Write-Host "Aviso: nenhum .nup com o ID do Zelda OoT (0400486024DEC000) no nome. Vou tentar com o maior .nup achado:"
        Write-Host "  $Nup"
    }
}
if (-not $Nup -and [Environment]::UserInteractive) {
    # nao achou nenhum: abre uma janela para voce escolher o arquivo
    try {
        Add-Type -AssemblyName System.Windows.Forms
        $dlg = New-Object System.Windows.Forms.OpenFileDialog
        $dlg.Title = 'Escolha o arquivo do jogo (.nup, Zelda Ocarina of Time v131072)'
        $dlg.Filter = 'Arquivo do jogo (*.nup)|*.nup|Todos os arquivos|*.*'
        if ($dlg.ShowDialog() -eq 'OK') { $Nup = $dlg.FileName }
    } catch {}
}
if (-not $Nup -or -not (Test-Path -LiteralPath $Nup)) {
    Write-Host 'Nao achei o arquivo do jogo (.nup, versao v131072). Rode de novo assim:'
    Write-Host '  .\build-game.ps1 -Nup "C:\caminho\The Legend of Zelda Ocarina of Time [0400486024DEC000][v131072].nup"'
    exit 2
}
# a versao vem no nome do arquivo; o build so aceita a v131072 e so reclamaria depois de minutos
if ((Split-Path $Nup -Leaf) -match '\[v(\d+)\]' -and $Matches[1] -ne '131072') {
    Write-Host "O arquivo e a versao v$($Matches[1]) do jogo. O RecompZel precisa da v131072. Use o .nup dessa versao." -ForegroundColor Red
    exit 2
}

# 2) pastas: mantem o layout do launcher (C:\DEV) se ele existir, senao usa uma pasta propria
if (-not $Out) {
    $Out = 'C:\Games\RecompZel'
    if (-not (Test-Path $Out) -and (Test-Path 'C:\Games\HookshotDev')) {   # pasta antiga: renomeie para RecompZel quando o jogo estiver fechado
        $Out = 'C:\Games\HookshotDev'
        Write-Host 'Aviso: usando a pasta antiga C:\Games\HookshotDev. Renomeie para C:\Games\RecompZel quando o jogo estiver fechado.'
    }
}
# C:\DEV so quando e o layout do launcher (C:\DEV\games.json); em qualquer outro PC usa %LOCALAPPDATA%\RecompZel
$base = if (Test-Path 'C:\DEV\games.json') { 'C:\DEV' } else { Join-Path $env:LOCALAPPDATA 'RecompZel' }
if (-not $Work) { $Work = Join-Path $base 'build-work' }
if (-not $Log)  { $Log  = Join-Path $base 'build.log' }

New-Item -ItemType Directory -Force -Path $Out, $Work, (Split-Path $Log) | Out-Null
Set-Location $Repo
Write-Host "Jogo:    $Nup"
Write-Host "Destino: $Out"
# NVIDIA DLSS (reescalonamento), so quando o launcher pede (-Dlss): baixa o SDK da NVIDIA, sob a licenca NVIDIA RTX SDKs aceita no launcher,
# e compila o motor com ele. Sem -Dlss o jogo e construido sem o SDK da NVIDIA.
$extra = @()
Remove-Item Env:HOOKSHOT_NGX_SDK -ErrorAction SilentlyContinue
if ($Dlss) {
    $env:HOOKSHOT_NGX_SDK = Join-Path $Work 'ngx-sdk'
    $extra = @('--fetch-ngx-sdk', '--accept-nvidia-license')
    Write-Host 'NVIDIA DLSS ligado: o SDK da NVIDIA sera baixado para o build (licenca aceita no launcher).'
}
Write-Host "Iniciando o build. Pode levar de dezenas de minutos a mais de uma hora. Nao feche esta janela."
Write-Host "Acompanhe em $Log"
$t0 = Get-Date
& $Py -I (Join-Path $Repo 'nx2\make_game.py') --nup $Nup --out $Out --work $Work --language pt-BR --fsr @extra --log $Log
$code = $LASTEXITCODE
$min = [math]::Round(((Get-Date) - $t0).TotalMinutes, 1)
Write-Host ""
Write-Host "Terminou com codigo $code em $min minutos."
Add-Content -Path $Log -Value "`r`n[script] codigo de saida $code, $min minutos" -Encoding UTF8

# 3) pos-instalacao: atalho na area de trabalho e "Jogar RecompZel.bat" na pasta do jogo
if ($code -eq 0 -and (Test-Path -LiteralPath (Join-Path $Out 'RecompZel.exe'))) {
    & (Join-Path $PSScriptRoot 'post-install.ps1') -GameDir $Out
}
exit $code
