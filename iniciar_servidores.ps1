Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "    INICIANDO AMBIENTE DE DESENVOLVIMENTO" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

if (!(Test-Path ".venv\Scripts\Activate.ps1")) {
    Write-Host "[ERRO] Pasta '.venv' nao encontrada neste diretorio!" -ForegroundColor Red
    Pause
    exit
}

if (!(Test-Path "package.json")) {
    Write-Host "[AVISO] Arquivo 'package.json' nao encontrado neste diretorio!" -ForegroundColor Yellow
}

Write-Host "[1/2] Abrindo terminal para o Uvicorn (API)..." -ForegroundColor Green
Write-Host "[2/2] Abrindo terminal para o Node.js (Frontend)..." -ForegroundColor Green
Write-Host ""
Write-Host "Os terminais do PowerShell foram abertos separadamente para monitoramento." -ForegroundColor DarkGray
Write-Host "------------------------------------------" -ForegroundColor DarkGray

Start-Process powershell -ArgumentList "-NoExit -Command `" & '.venv\Scripts\Activate.ps1'; uvicorn api:app --reload `" "
Start-Process powershell -ArgumentList "-NoExit -Command `" npm run dev `" "