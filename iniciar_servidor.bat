@echo off
cd /d "%~dp0"

:: Adiciona a pasta node_portable (que está na raiz do projeto) ao PATH
set "PATH=%~dp0node_portable;%PATH%"

:: Inicia o script do PowerShell
powershell -ExecutionPolicy Bypass -File "iniciar_servidores.ps1"
pause