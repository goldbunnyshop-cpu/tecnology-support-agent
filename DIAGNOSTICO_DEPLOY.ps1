# DIAGNOSTICO_DEPLOY.ps1 — Verificar qué se hizo push

Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  DIAGNÓSTICO: Verificar qué se hizo push a GitHub" -ForegroundColor Cyan
Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

cd C:\Users\Elitebook\whatsapp-agentkit

# Paso 1: Verificar últimos commits
Write-Host "[1/4] Últimos commits en GitHub:" -ForegroundColor Yellow
git log --oneline -10
Write-Host ""

# Paso 2: Verificar archivo memory.py
Write-Host "[2/4] Estado de agent/memory.py:" -ForegroundColor Yellow
$lastModMemory = git log -1 --format="%ai" -- agent/memory.py
Write-Host "      Última modificación: $lastModMemory"
if (git show HEAD:agent/memory.py | Select-String "StoppedNumber" -Quiet) {
    Write-Host "      ✅ StoppedNumber ESTÁ en GitHub" -ForegroundColor Green
} else {
    Write-Host "      ❌ StoppedNumber NO está en GitHub" -ForegroundColor Red
}
Write-Host ""

# Paso 3: Verificar archivo commands_control.py
Write-Host "[3/4] Estado de agent/commands_control.py:" -ForegroundColor Yellow
if (git ls-files | Select-String "agent/commands_control.py" -Quiet) {
    Write-Host "      ✅ Archivo EXISTE en GitHub" -ForegroundColor Green
} else {
    Write-Host "      ❌ Archivo NO existe en GitHub" -ForegroundColor Red
}
Write-Host ""

# Paso 4: Verificar archivo pricing_integration.py
Write-Host "[4/4] Estado de agent/pricing_integration.py:" -ForegroundColor Yellow
if (git ls-files | Select-String "agent/pricing_integration.py" -Quiet) {
    Write-Host "      ✅ Archivo EXISTE en GitHub" -ForegroundColor Green
} else {
    Write-Host "      ❌ Archivo NO existe en GitHub" -ForegroundColor Red
}
Write-Host ""

Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  CONCLUSIÓN" -ForegroundColor Cyan
Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "Si STOP/ON NO está en GitHub, ejecuta:" -ForegroundColor Yellow
Write-Host "  .\PUSH_STOP_ON.ps1" -ForegroundColor White
Write-Host ""
Write-Host "Si MercadoLibre NO está en GitHub, ejecuta:" -ForegroundColor Yellow
Write-Host "  git add agent/pricing_integration.py agent/brain.py" -ForegroundColor White
Write-Host "  git commit -m 'feat: integración MercadoLibre como fallback'" -ForegroundColor White
Write-Host "  git push origin main" -ForegroundColor White
Write-Host ""
