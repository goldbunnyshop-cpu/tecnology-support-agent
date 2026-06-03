# Script para hacer push de cambios a GitHub y Railway
# Uso: .\push-changes.ps1

Write-Host "================================" -ForegroundColor Cyan
Write-Host "  Push a GitHub + Railway Deploy" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Verificar si estamos en un repositorio Git
if (-not (Test-Path .git)) {
    Write-Host "ERROR: No estamos en un repositorio Git" -ForegroundColor Red
    exit 1
}

# 1. Mostrar estado actual
Write-Host "[1/4] Estado actual del repositorio:" -ForegroundColor Yellow
git status --short
Write-Host ""

# 2. Agregar cambios
Write-Host "[2/4] Agregando cambios..." -ForegroundColor Yellow
git add -A
Write-Host "Cambios agregados" -ForegroundColor Green
Write-Host ""

# 3. Commit
$mensaje = "fix: CRITICO - mejorar scoring Google Sheets - seleccionar precio mas alto en empates"
Write-Host "[3/4] Haciendo commit: '$mensaje'" -ForegroundColor Yellow
git commit -m $mensaje
if ($LASTEXITCODE -eq 0) {
    Write-Host "Commit realizado" -ForegroundColor Green
} else {
    Write-Host "! No hay cambios para hacer commit" -ForegroundColor Cyan
}
Write-Host ""

# 4. Push a GitHub (y Railway detecta automáticamente)
Write-Host "[4/4] Haciendo push a GitHub (Railway se actualizara automaticamente)..." -ForegroundColor Yellow
git push origin main
if ($LASTEXITCODE -eq 0) {
    Write-Host "Push realizado exitosamente" -ForegroundColor Green
    Write-Host ""
    Write-Host "================================" -ForegroundColor Green
    Write-Host "  Cambios desplegados!" -ForegroundColor Green
    Write-Host "================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Railway deberia detectar el push automaticamente." -ForegroundColor Cyan
    Write-Host "Verifica en: https://railway.app" -ForegroundColor Cyan
} else {
    Write-Host "ERROR: El push fallo" -ForegroundColor Red
    exit 1
}
