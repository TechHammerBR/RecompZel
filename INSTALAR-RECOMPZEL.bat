@echo off
rem RecompZel: instala e cria o atalho para jogar. Duplo clique.
rem Precisa do seu proprio arquivo do jogo (.nup). Veja o README.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0recompzel\instalar.ps1"
echo.
pause
