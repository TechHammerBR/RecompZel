# Compila o jogo a partir do seu .nup, usando as ferramentas de compilacao do RecompZel/Hookshot Builder.
# Uso:  powershell -ExecutionPolicy Bypass -File .\build-game.ps1 [-Nup <arquivo.nup>] [-Out <pasta do jogo>]
# Sem parametros: procura o .nup em Downloads, Desktop e Documentos e instala em C:\Games\RecompZel (ou %USERPROFILE%\Games\RecompZel).
# Ao terminar com sucesso, cria o atalho na area de trabalho (post-install.ps1).
param([string]$Nup, [string]$Out, [string]$Work, [string]$Log, [switch]$Dlss)
$ErrorActionPreference = 'Continue'
# Aberto pelo launcher (RZ_PAUSE=1) a janela fecha sozinha quando da certo; se falhar, espera um Enter para dar tempo de ler o erro.
function Pause-Fechar { if ($env:RZ_PAUSE -eq '1') { Read-Host 'Pressione Enter para fechar esta janela' | Out-Null } }
trap { Write-Host ('ERRO: ' + $_) -ForegroundColor Red; Pause-Fechar; exit 1 }
. (Join-Path $PSScriptRoot 'env-recompzel.ps1')
[System.Diagnostics.Process]::GetCurrentProcess().PriorityClass = 'BelowNormal'   # o PC continua utilizavel durante o build

# 1) arquivo do jogo
$informado = [bool]$Nup
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
        Write-Host 'Nao achei o arquivo do jogo. Abrindo uma janela para voce escolher o .nup (se nao aparecer, olhe a barra de tarefas)...'
        Add-Type -AssemblyName System.Windows.Forms
        $dlg = New-Object System.Windows.Forms.OpenFileDialog
        $dlg.Title = 'Escolha o arquivo do jogo (.nup, Zelda Ocarina of Time v131072)'
        $dlg.Filter = 'Arquivo do jogo (*.nup)|*.nup|Todos os arquivos|*.*'
        # um dono TopMost e invisivel: a janela abre na frente das outras, nao escondida atras do console
        $dono = New-Object System.Windows.Forms.Form
        $dono.TopMost = $true
        $dono.ShowInTaskbar = $false
        if ($dlg.ShowDialog($dono) -eq 'OK') { $Nup = $dlg.FileName }
        $dono.Dispose()
    } catch {}
}
if ($informado -and -not (Test-Path -LiteralPath $Nup)) {
    Write-Host "O arquivo informado nao existe: $Nup" -ForegroundColor Red
    Pause-Fechar
    exit 2
}
if (-not $Nup -or -not (Test-Path -LiteralPath $Nup)) {
    Write-Host 'Nao achei o arquivo do jogo (.nup, versao v131072). Rode de novo assim:'
    Write-Host '  .\build-game.ps1 -Nup "C:\caminho\The Legend of Zelda Ocarina of Time [0400486024DEC000][v131072].nup"'
    Pause-Fechar
    exit 2
}
# a versao vem no nome do arquivo; o build so aceita a v131072 e so reclamaria depois de minutos
if ((Split-Path $Nup -Leaf) -match '\[v(\d+)\]' -and $Matches[1] -ne '131072') {
    Write-Host "O arquivo e a versao v$($Matches[1]) do jogo. O RecompZel precisa da v131072. Use o .nup dessa versao." -ForegroundColor Red
    Pause-Fechar
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
# mesma regra do launcher: a pasta dos scripts (C:\DEV no PC do desenvolvedor, %LOCALAPPDATA%\RecompZel com o .exe); rodando de dentro do repositorio, %LOCALAPPDATA%\RecompZel
$base = if ((Split-Path $PSScriptRoot -Leaf) -eq 'recompzel' -and (Test-Path (Join-Path (Split-Path $PSScriptRoot -Parent) 'nx2\make_game.py'))) { Join-Path $env:LOCALAPPDATA 'RecompZel' } else { $PSScriptRoot }
if (-not $Work) { $Work = Join-Path $base 'build-work' }
if (-not $Log)  { $Log  = Join-Path $base 'build.log' }

New-Item -ItemType Directory -Force -Path $Out, $Work, (Split-Path $Log) | Out-Null

# Codigo do jogo: se $Repo e um clone git (C:\DEV\RecompZel), traz do GitHub o que for novo antes de compilar. Sem isso o build usava o codigo
# da ultima vez que o clone foi atualizado a mao: um build "na ultima versao" saia com o motor antigo. So AVANCA (git merge --ff-only):
# se o clone tem alteracoes suas, commits que o GitHub nao tem, ou esta em outro ramo, avisa e nao mexe em nada. A copia baixada pelo launcher
# (sem .git) nao passa por aqui: o botao Atualizar cuida dela.
function Update-Clone {
    if (-not (Test-Path -LiteralPath (Join-Path $Repo '.git'))) { return }
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Write-Host 'Aviso: git nao encontrado; compilando o codigo que esta no disco.'; return }
    Push-Location -LiteralPath $Repo
    try {
        $antes = (& git rev-parse --short HEAD 2>$null)
        & git fetch --quiet origin main 2>$null
        if ($LASTEXITCODE -ne 0) { Write-Host "Aviso: nao consegui consultar o GitHub (sem internet?). Compilando o codigo que esta no disco ($antes)."; return }
        $atras = [int](& git rev-list --count 'HEAD..origin/main' 2>$null)
        $a_frente = [int](& git rev-list --count 'origin/main..HEAD' 2>$null)
        $ramo = (& git rev-parse --abbrev-ref HEAD 2>$null)
        $sujo = @(& git status --porcelain --untracked-files=no 2>$null)
        if ($atras -eq 0) { Write-Host "Codigo do jogo: $antes (ja e o mais novo do GitHub)."; return }
        if ($ramo -ne 'main' -or $a_frente -gt 0 -or $sujo.Count -gt 0) {
            Write-Host "AVISO: o GitHub tem $atras commit(s) novo(s), mas nao atualizei o clone porque ele tem alteracoes suas (ramo $ramo, $a_frente commit(s) so seus, $($sujo.Count) arquivo(s) modificado(s))." -ForegroundColor Yellow
            Write-Host "       Compilando o codigo que esta no disco ($antes). Para atualizar, rode 'Sincronizar GitHub.bat' e compile de novo."
            return
        }
        & git merge --ff-only origin/main 2>&1 | Out-Null
        $mesclou = ($LASTEXITCODE -eq 0)   # (antes do git rev-parse, que reescreve o codigo de saida)
        $depois = (& git rev-parse --short HEAD 2>$null)
        if ($mesclou -and $depois -ne $antes) { Write-Host "Codigo do jogo atualizado: $antes -> $depois ($atras commit(s) novo(s) do GitHub)." }
        else { Write-Host "AVISO: nao consegui atualizar o clone ($antes). Compilando o que esta no disco." -ForegroundColor Yellow }
    } finally { Pop-Location }
}
Update-Clone
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
if ($code -ne 0) { Pause-Fechar }
exit $code
