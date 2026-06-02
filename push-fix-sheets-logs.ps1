# Script para push de fixes de logging en Google Sheets
# Ejecutar desde PowerShell en el directorio del proyecto

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Push: Fixes de logging para Google Sheets" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. Verificar directorio
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
Write-Host "[INFO] Cambios detectados:" -ForegroundColor Yellow
git status --short | Select-String "pricing_sheets|pricing_fallback"
Write-Host ""

# 4. Agregar archivos
Write-Host "[INFO] Agregando archivos..." -ForegroundColor Yellow
git add agent/pricing_sheets.py agent/pricing_fallback.py
Write-Host "[OK] Archivos agregados" -ForegroundColor Green
Write-Host ""

# 5. Hacer commit
Write-Host "[INFO] Haciendo commit..." -ForegroundColor Yellow
git commit -m "fix: agregar logs detallados para diagnosticar fallback de Google Sheets

agent/pricing_sheets.py:
- Log antes de descargar cada hoja (DISPLAYS, BATERIAS ANDROID, BATERIAS iPHONE)
- Log si se pudo descargar o si CSV estuvo vacio
- Log de items parseados por cada hoja
- Log desde caché si disponible

agent/pricing_fallback.py:
- Log antes de llamar cotizar_google_sheets
- Log de respuesta (None o dict)
- Try/except con exc_info=True para ver stack trace
- Diagnosticar por que NO aparecen [SHEETS] en Railway logs"

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
Write-Host "[1] Railway redeploy automatico (~2 minutos)"
Write-Host "[2] Una vez que este Online, prueba:"
Write-Host "    - Envia: 'precio bateria moto g85'"
Write-Host "[3] Revisa los logs NEW en Railway:"
Write-Host "    - Busca por '[SHEETS]' y '[PRICING]'"
Write-Host "    - Si ves las nuevas lineas de log,"
Write-Host "      sabremos exactamente donde falla"
Write-Host ""
