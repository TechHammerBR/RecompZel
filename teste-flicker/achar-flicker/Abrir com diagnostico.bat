@echo off
rem Busca do shader do flicker azulado: abre o jogo com o diagnostico e conduz a busca por metades.
rem Coloque a pasta achar-flicker DENTRO da pasta do jogo (onde esta o RecompZel.exe) e de dois cliques aqui.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0achar-shader.ps1"
