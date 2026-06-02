# Script para hacer push de la integracion Google Sheets
# Ejecutar desde PowerShell en el directorio del proyecto

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Push: Integracion Google Sheets - Fase 5" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. Verificar que estamos en el directorio correcto
if (-not (Test-Path ".git")) {
    Write-Host "[ERROR] No estamos en la raiz del repositorio git" -ForegroundColor Red
    exit 1
}

Write-Host "[OK] Directorio del proyecto detectado" -ForegroundColor Green
Write-Host ""

# 2. Limpiar el lock file si existe
if (Test-Path ".git/index.lock") {
    Write-Host "[INFO] Limpiando git lock file..." -ForegroundColor Yellow
    Remove-Item ".git/index.lock" -Force
    Write-Host "[OK] Lock file eliminado" -ForegroundColor Green
    Write-Host ""
}

# 2. Ver estado actual
Write-Host "[INFO] Estado actual del repositorio:" -ForegroundColor Yellow
git status --short | Select-String "pricing_sheets|pricing_fallback|KNOWLEDGE_BASE"
Write-Host ""

# 3. Agregar los archivos especificos
Write-Host "[INFO] Agregando archivos..." -ForegroundColor Yellow
git add agent/pricing_sheets.py
git add tests/test_pricing_sheets.py
git add agent/pricing_fallback.py
git add KNOWLEDGE_BASE_CONSOLIDATED.md
Write-Host "[OK] Archivos agregados" -ForegroundColor Green
Write-Host ""

# 4. Hacer commit
Write-Host "[INFO] Haciendo commit..." -ForegroundColor Yellow
git commit -m "feat: integracion Google Sheets como fuente de precios numero 2

- Modulo pricing_sheets.py: lectura y parseo de 3 hojas
- DISPLAYS: 18 items
- BATERIAS ANDROID: 212 items
- BATERIAS iPHONE: 99 items
- Tests de integracion en test_pricing_sheets.py
- Integracion en pipeline de precios: Hugo Shop -> Google Sheets -> MercadoLibre
- Cache con TTL de 1 hora para optimizar API calls
- Consolidacion de knowledge base en documento unico

Variables de entorno agregadas en Railway:
- GOOGLE_SHEETS_ID=1sMVr7rUp2dz_4h4NUEwFjH-iVqOjUWjJNYx5ptfgT2U
- PRICING_SHEETS_CACHE_TTL=3600"

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Error en git commit" -ForegroundColor Red
    exit 1
}

Write-Host "[OK] Commit exitoso" -ForegroundColor Green
Write-Host ""

# 5. Hacer push
Write-Host "[INFO] Haciendo push a GitHub (esto activara redeploy en Railway)..." -ForegroundColor Yellow
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
Write-Host "[2] Verifica que el servicio siga Online en:"
Write-Host "    https://railway.com/dashboard"
Write-Host "[3] Una vez Online, prueba en el grupo interno:"
Write-Host "    - Envia: 'precio display iphone 15'"
Write-Host "    - Espera que responda con precio de Google Sheets"
Write-Host "[4] Si hay error, verifica los logs en Railway"
Write-Host ""
