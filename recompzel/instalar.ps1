# instalar.ps1 - instala o RecompZel do zero (chamado por INSTALAR-RECOMPZEL.bat).
# 1) confere o PC  2) acha o seu .nup  3) compila (baixando as ferramentas na primeira vez)  4) cria o atalho para jogar.
# Voce precisa do seu proprio arquivo do jogo (.nup, v131072). Nada do jogo e baixado ou distribuido.
param([string]$Nup, [string]$Out)
$ErrorActionPreference = 'Continue'
Write-Host ''
Write-Host '=== RecompZel: Zelda Ocarina of Time (Switch 2) no PC ===' -ForegroundColor Cyan
Write-Host 'Este e o projeto RecompZel (fork do Hookshot). Nao use os instaladores do repositorio original.'
Write-Host ''

# Checagem rapida do PC (so avisa; quem decide e voce). O build leva de dezenas de minutos a mais de uma hora.
$aviso = @()
if (-not [Environment]::Is64BitOperatingSystem) { Write-Host 'Este PC e Windows de 32 bits. O RecompZel precisa de Windows 64 bits.' -ForegroundColor Red; exit 1 }
try {
    $ramGb = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)
    if ($ramGb -lt 16) { $aviso += "Memoria: $ramGb GB. O recomendado para o build e 16 GB ou mais." }
} catch {}
try {
    $drv = if ($Out) { Split-Path -Qualifier $Out } else { 'C:' }
    $livreGb = [math]::Round((Get-PSDrive ($drv.TrimEnd(':'))).Free / 1GB)
    if ($livreGb -lt 60) { $aviso += "Espaco livre em ${drv}: $livreGb GB. O build usa cerca de 60 GB." }
} catch {}
try {
    # so avisa se nenhuma placa for reconhecida como NVIDIA GTX 16xx/RTX, AMD RX 6000 ou mais nova, ou Intel Arc (Vulkan com mesh shaders)
    $gpus = @(Get-CimInstance Win32_VideoController | ForEach-Object { $_.Name })
    $ok = $gpus | Where-Object { $_ -match 'RTX|GTX 16|Radeon RX [6-9]\d{3}|Arc' }
    if (-not $ok) { $aviso += ('A placa de video (' + ($gpus -join ', ') + ') pode nao suportar Vulkan com mesh shaders (precisa de NVIDIA GTX 16xx/RTX, AMD RX 6000 ou mais nova, ou Intel Arc). Deixe o driver atualizado.') }
} catch {}
foreach ($a in $aviso) { Write-Host ('Aviso: ' + $a) -ForegroundColor Yellow }
Write-Host ''

# (as ferramentas de compilacao e o codigo-fonte sao baixados sozinhos pelo build-game.ps1 na primeira vez, se faltarem)
$args2 = @{}
if ($Nup) { $args2.Nup = $Nup }
if ($Out) { $args2.Out = $Out }
& (Join-Path $PSScriptRoot 'build-game.ps1') @args2
if ($LASTEXITCODE -ne 0) { Write-Host 'O build nao terminou. Veja a mensagem acima.' -ForegroundColor Yellow; exit $LASTEXITCODE }
Write-Host ''
Write-Host 'Instalado. Abra "Zelda OoT (RecompZel)" na area de trabalho para jogar.' -ForegroundColor Green
