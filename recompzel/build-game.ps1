# Compila o jogo a partir do seu .nup, usando as ferramentas de compilacao do RecompZel/Hookshot Builder.
# Uso:  powershell -ExecutionPolicy Bypass -File .\build-game.ps1 [-Nup <arquivo.nup>] [-Out <pasta do jogo>]
# Sem parametros: procura o .nup em Downloads, Desktop e Documentos e instala em C:\Games\RecompZel (ou %USERPROFILE%\Games\RecompZel).
# Ao terminar com sucesso, cria o atalho na area de trabalho (post-install.ps1).
param([string]$Nup, [string]$Out, [string]$Work, [string]$Log)
$ErrorActionPreference = 'Continue'
. (Join-Path $PSScriptRoot 'env-recompzel.ps1')
[System.Diagnostics.Process]::GetCurrentProcess().PriorityClass = 'BelowNormal'   # o PC continua utilizavel durante o build

# 1) arquivo do jogo
if (-not $Nup) {
    $dirs = @('Downloads', 'Desktop', 'Documents') | ForEach-Object { Join-Path $env:USERPROFILE $_ } | Where-Object { Test-Path $_ }
    $Nup = Get-ChildItem -Path $dirs -Recurse -File -Filter '*.nup' -ErrorAction SilentlyContinue |
           Where-Object { $_.Name -like '*0400486024DEC000*' } | Sort-Object Length -Descending |
           Select-Object -First 1 -ExpandProperty FullName
}
if (-not $Nup -or -not (Test-Path -LiteralPath $Nup)) {
    Write-Host 'Nao achei o arquivo do jogo (.nup, versao v131072). Rode de novo assim:'
    Write-Host '  .\build-game.ps1 -Nup "C:\caminho\The Legend of Zelda Ocarina of Time [0400486024DEC000][v131072].nup"'
    exit 2
}

# 2) pastas: mantem o layout antigo (C:\DEV) se ele existir, senao usa uma pasta propria
if (-not $Out) {
    $Out = 'C:\Games\RecompZel'
    if (-not (Test-Path $Out) -and (Test-Path 'C:\Games\HookshotDev')) {   # pasta antiga: renomeie para RecompZel quando o jogo estiver fechado
        $Out = 'C:\Games\HookshotDev'
        Write-Host 'Aviso: usando a pasta antiga C:\Games\HookshotDev. Renomeie para C:\Games\RecompZel quando o jogo estiver fechado.'
    }
}
$base = if (Test-Path 'C:\DEV') { 'C:\DEV' } else { Join-Path $env:LOCALAPPDATA 'RecompZel' }
if (-not $Work) { $Work = Join-Path $base 'build-work' }
if (-not $Log)  { $Log  = Join-Path $base 'build.log' }

New-Item -ItemType Directory -Force -Path $Out, $Work, (Split-Path $Log) | Out-Null
Set-Location $Repo
Write-Host "Jogo:    $Nup"
Write-Host "Destino: $Out"
Write-Host "Iniciando o build. Pode levar de dezenas de minutos a mais de uma hora. Nao feche esta janela."
Write-Host "Acompanhe em $Log"
$t0 = Get-Date
& $Py -I (Join-Path $Repo 'nx2\make_game.py') --nup $Nup --out $Out --work $Work --language pt-BR --fsr --log $Log
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
