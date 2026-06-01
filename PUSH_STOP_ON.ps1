# PUSH_STOP_ON.ps1 — Script para hacer push del sistema STOP/ON
# Ejecutar en PowerShell desde la raíz del proyecto

Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  PUSH: Sistema STOP/ON" -ForegroundColor Cyan
Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

$proyecto = "C:\Users\Elitebook\whatsapp-agentkit"
Set-Location $proyecto

# Paso 1: Eliminar lock si existe
Write-Host "[1/5] Limpiando locks de git..." -ForegroundColor Yellow
if (Test-Path ".git\index.lock") {
    Remove-Item ".git\index.lock" -Force
    Write-Host "      ✓ Lock eliminado" -ForegroundColor Green
}
else {
    Write-Host "      ✓ Sin locks" -ForegroundColor Green
}
Write-Host ""

# Paso 2: Reset staged files
Write-Host "[2/5] Resetando archivos staged..." -ForegroundColor Yellow
git reset HEAD
Write-Host "      ✓ Reset completado" -ForegroundColor Green
Write-Host ""

# Paso 3: Agregar solo archivos STOP/ON
Write-Host "[3/5] Agregando archivos STOP/ON..." -ForegroundColor Yellow
$archivos = @(
    "agent/memory.py",
    "agent/main.py",
    "agent/commands_control.py",
    "COMANDO_STOP_ON_GUIA.md",
    "CAMBIOS_STOP_ON_2026_06_01.md",
    "test_stop_on.py",
    "PUSH_STOP_ON.ps1",
    "ESTADO_ACTUAL_2026_06_01.md"
)

foreach ($archivo in $archivos) {
    if (Test-Path $archivo) {
        git add $archivo
        Write-Host "      ✓ $archivo" -ForegroundColor Green
    }
    else {
        Write-Host "      ✗ NO ENCONTRADO: $archivo" -ForegroundColor Red
    }
}
Write-Host ""

# Paso 4: Verificar cambios
Write-Host "[4/5] Verificando cambios..." -ForegroundColor Yellow
git status --short
Write-Host ""

# Paso 5: Commit y Push
Write-Host "[5/5] Commit y Push..." -ForegroundColor Yellow
$commitMsg = "feat: sistema STOP/ON para control permanente de números"
git commit -m $commitMsg
if ($LASTEXITCODE -eq 0) {
    Write-Host "      ✓ Commit exitoso" -ForegroundColor Green
}
else {
    Write-Host "      ✗ Error en commit" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Haciendo push a main..." -ForegroundColor Yellow
git push origin main
if ($LASTEXITCODE -eq 0) {
    Write-Host "      ✓ Push exitoso" -ForegroundColor Green
}
else {
    Write-Host "      ✗ Error en push" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "  ✅ PUSH COMPLETADO - Railway está redeployando..." -ForegroundColor Green
Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Write-Host "Próximos pasos:" -ForegroundColor Cyan
Write-Host "  1. Esperar 2 minutos para Railway redeploy" -ForegroundColor Cyan
Write-Host "  2. Abrir grupo 'Taller Interno TS'" -ForegroundColor Cyan
Write-Host "  3. Ejecutar: stop: 5527777777" -ForegroundColor Cyan
Write-Host "  4. Verificar respuesta: 🛑 DETENIDO: 5527777777" -ForegroundColor Cyan
Write-Host ""
