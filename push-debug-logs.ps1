# Script para hacer push del fix de logs
# Ejecutar desde PowerShell en el directorio del proyecto

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Push: Fix de logs para Google Sheets" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. Verificar que estamos en el directorio correcto
if (-not (Test-Path ".git")) {
    Write-Host "[ERROR] No estamos en la raiz del repositorio git" -ForegroundColor Red
    exit 1
}

Write-Host "[OK] Directorio del proyecto detectado" -ForegroundColor Green
Write-Host ""

# 2. Limpiar git lock si existe
if (Test-Path ".git/index.lock") {
    Write-Host "[INFO] Limpiando git lock file..." -ForegroundColor Yellow
    Remove-Item ".git/index.lock" -Force -ErrorAction SilentlyContinue
    Write-Host "[OK] Lock file eliminado" -ForegroundColor Green
    Write-Host ""
}

# 3. Ver estado
Write-Host "[INFO] Estado actual:" -ForegroundColor Yellow
git status --short | Select-String "pricing_sheets"
Write-Host ""

# 4. Agregar archivos
Write-Host "[INFO] Agregando archivos..." -ForegroundColor Yellow
git add agent/pricing_sheets.py

# 5. Hacer commit
Write-Host "[INFO] Haciendo commit..." -ForegroundColor Yellow
git commit -m "fix: agregar logs detallados para diagnosticar fallos de Google Sheets

- Agregar logs en _cargar_catalogo_sheets para ver si se descarga cada hoja
- Agregar logs para ver si se estan parseando los items
- Logs para diagnosticar por que NO aparecen [SHEETS] en los logs de Railway"

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Error en git commit" -ForegroundColor Red
    exit 1
}

Write-Host "[OK] Commit exitoso" -ForegroundColor Green
Write-Host ""

# 6. Hacer push
Write-Host "[INFO] Haciendo push a GitHub..." -ForegroundColor Yellow
git push origin main

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Error en git push" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[OK] Push completado exitosamente" -ForegroundColor Green
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "PROXIMOS PASOS:" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "[1] Railway hara redeploy automatico (~2 minutos)"
Write-Host "[2] Vuelve a probar en el grupo interno:"
Write-Host "    - Envia: 'precio bateria moto g85'"
Write-Host "[3] Revisa los logs en Railway:"
Write-Host "    - Busca por '[SHEETS]' para ver los logs detallados"
Write-Host "[4] Si ves '[SHEETS]' significa que el modulo se esta ejecutando"
Write-Host ""
