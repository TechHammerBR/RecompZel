# instalar.ps1 - instala o RecompZel do zero (chamado por INSTALAR-RECOMPZEL.bat).
# 1) confere as ferramentas de compilacao  2) acha o seu .nup  3) compila  4) cria o atalho para jogar.
# Voce precisa do seu proprio arquivo do jogo (.nup, v131072). Nada do jogo e baixado ou distribuido.
param([string]$Nup, [string]$Out)
$ErrorActionPreference = 'Continue'
Write-Host ''
Write-Host '=== RecompZel: Zelda Ocarina of Time (Switch 2) no PC ===' -ForegroundColor Cyan
Write-Host 'Este e o projeto RecompZel (fork do Hookshot). Nao use os instaladores do repositorio original.'
Write-Host ''

try { . (Join-Path $PSScriptRoot 'env-recompzel.ps1') } catch {
    Write-Host $_.Exception.Message -ForegroundColor Yellow
    Write-Host ''
    Write-Host 'Baixe o RecompZelBuilder.exe na aba Releases do repositorio TechHammerBR/RecompZel,'
    Write-Host 'rode uma vez (ele baixa as ferramentas), feche, e abra INSTALAR-RECOMPZEL.bat de novo.'
    exit 1
}
$args2 = @{}
if ($Nup) { $args2.Nup = $Nup }
if ($Out) { $args2.Out = $Out }
& (Join-Path $PSScriptRoot 'build-game.ps1') @args2
if ($LASTEXITCODE -ne 0) { Write-Host 'O build nao terminou. Veja a mensagem acima.' -ForegroundColor Yellow; exit $LASTEXITCODE }
Write-Host ''
Write-Host 'Instalado. Abra "Zelda OoT (RecompZel)" na area de trabalho para jogar.' -ForegroundColor Green
