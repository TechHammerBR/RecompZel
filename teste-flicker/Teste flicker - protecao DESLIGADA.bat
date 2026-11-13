@echo off
rem Teste do flicker de cor (cena inteira muda de tom por um quadro).
rem RX_VK_PROTECT_BARE=0: desliga a protecao que a versao Ultimate liga por padrao. Se o flicker sumir, achamos a causa.
rem Abre o launcher normal (com todas as suas opcoes) e o jogo herda a variavel abaixo. Nada fica gravado no Windows.
cd /d "%~dp0"
set RX_VK_PROTECT_BARE=0
if exist "%~dp0RecompZel Launcher.exe" (
    start "" "%~dp0RecompZel Launcher.exe"
) else if exist "%~dp0RecompZel.exe" (
    if exist "%~dp0pular-shaders.txt" set "RX_VK_SKIP_FILE=%~dp0pular-shaders.txt"
    start "" "%~dp0RecompZel.exe"
) else (
    echo Coloque este arquivo na mesma pasta do "RecompZel Launcher.exe" ou do "RecompZel.exe".
    pause
)
