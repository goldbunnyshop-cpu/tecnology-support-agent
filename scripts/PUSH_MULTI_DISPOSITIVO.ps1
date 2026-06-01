# Script de Push para arquitectura multi-dispositivo
# Cambios: Celular (cotización) | Consola (diagnóstico) | Laptop (ambos)

Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  PUSH: Arquitectura Multi-Dispositivo + Cross-sell" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# 1. Verificar estado
Write-Host "1️⃣  Verificando estado de git..." -ForegroundColor Yellow
git status

Write-Host ""
Write-Host "2️⃣  Agregando cambios..." -ForegroundColor Yellow
git add -A

Write-Host ""
Write-Host "3️⃣  Committeando..." -ForegroundColor Yellow
$mensaje = "feat: arquitectura multi-dispositivo con cross-sell (celular/consola/laptop)"
git commit -m $mensaje

Write-Host ""
Write-Host "4️⃣  Pusheando a origin..." -ForegroundColor Yellow
git push origin main

Write-Host ""
Write-Host "✅ Push completado!" -ForegroundColor Green
Write-Host ""
Write-Host "Próximos pasos:" -ForegroundColor Cyan
Write-Host "1. Ve a https://dashboard.railway.app" -ForegroundColor Cyan
Write-Host "2. El redeploy comenzará automáticamente" -ForegroundColor Cyan
Write-Host "3. Espera 5-10 minutos a que se completen los builds" -ForegroundColor Cyan
Write-Host ""
Write-Host "Para ver logs en tiempo real:" -ForegroundColor Gray
Write-Host "railway logs" -ForegroundColor Gray
