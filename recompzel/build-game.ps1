# Compila o jogo a partir do seu .nup, usando as ferramentas do HookshotBuilder.
# Saida do jogo:  C:\Games\HookshotDev     Arquivos temporarios:  C:\DEV\build-work     Log:  C:\DEV\build.log
# Uso: cd C:\DEV ; powershell -ExecutionPolicy Bypass -File .\build-game.ps1
# --fsr: compila o suporte ao AMD FSR 4 (as DLLs da AMD ou do fsr4vk ficam na pasta do jogo, nao vem nada junto)
$ErrorActionPreference = 'Continue'
. 'C:\DEV\env-recompzel.ps1'
[System.Diagnostics.Process]::GetCurrentProcess().PriorityClass = 'BelowNormal'   # o PC continua utilizavel durante o build

$nup  = 'C:\Users\Crann\Downloads\Zeldinha\The Legend of Zelda Ocarina of Time [0400486024DEC000][v131072].nup'
$out  = 'C:\Games\HookshotDev'
$work = 'C:\DEV\build-work'
$log  = 'C:\DEV\build.log'

New-Item -ItemType Directory -Force -Path $out, $work | Out-Null
Set-Location $Repo
Write-Host "Iniciando o build. Pode levar de dezenas de minutos a mais de uma hora. Nao feche esta janela."
Write-Host "Acompanhe em $log"
$t0 = Get-Date
& $Py -I (Join-Path $Repo 'nx2\make_game.py') --nup $nup --out $out --work $work --language pt-BR --fsr --log $log
$code = $LASTEXITCODE
$min = [math]::Round(((Get-Date) - $t0).TotalMinutes, 1)
Write-Host ""
Write-Host "Terminou com codigo $code em $min minutos."
Add-Content -Path 'C:\DEV\build.log' -Value "`r`n[script] codigo de saida $code, $min minutos" -Encoding UTF8
