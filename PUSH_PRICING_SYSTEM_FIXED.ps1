# Script PowerShell para push del pricing system
# Version sin caracteres especiales para evitar errores de encoding

Write-Host ""
Write-Host "================================"
Write-Host "  PUSH PRICING SYSTEM"
Write-Host "================================"
Write-Host ""

cd C:\Users\Elitebook\whatsapp-agentkit

# 1. LIMPIAR .git corrupto
Write-Host "[1/6] Limpiando .git corrupto..." -ForegroundColor Yellow

if (Test-Path .git) {
    try {
        Rename-Item .git -NewName .git_old_backup -Force -ErrorAction SilentlyContinue
        Write-Host "OK: .git renombrado a .git_old_backup" -ForegroundColor Green
        Write-Host ""
    } catch {
        Write-Host "ADVERTENCIA: No se pudo renombrar .git" -ForegroundColor Yellow
        Write-Host ""
    }
}

# 2. INICIALIZAR GIT
Write-Host "[2/6] Re-inicializando git..." -ForegroundColor Yellow

git init
git config user.email "goldbunnyshop@gmail.com"
git config user.name "Christian"
git remote add origin https://github.com/goldbunnyshop-cpu/tecnology-support-agent.git

Write-Host "OK: Git re-inicializado" -ForegroundColor Green
Write-Host ""

# 3. TRAER CODIGO REMOTO
Write-Host "[3/6] Descargando codigo remoto de GitHub..." -ForegroundColor Yellow

git fetch origin main:main --force
git checkout main

Write-Host "OK: Rama main actualizada" -ForegroundColor Green
Write-Host ""

# 4. AGREGAR ARCHIVOS DEL PRICING SYSTEM
Write-Host "[4/6] Agregando archivos del pricing system..." -ForegroundColor Yellow

git add agent/pricing.py
git add agent/pausa_manager.py
git add agent/pricing_scheduler.py
git add agent/brain_enhanced.py
git add agent/main.py

Write-Host ""
Write-Host "Archivos a commitear:" -ForegroundColor Cyan
git status --short

Write-Host ""
Write-Host "OK: Archivos agregados" -ForegroundColor Green
Write-Host ""

# 5. HACER COMMIT
Write-Host "[5/6] Creando commit..." -ForegroundColor Yellow

git commit -m "feat: activar sistema de pricing con cotizacion multi-fuente y comando @pausa

- Agrega agent/pricing.py: motor de cotizacion inteligente
- Agrega agent/pausa_manager.py: comando @pausa para escalado manual
- Agrega agent/pricing_scheduler.py: scheduler APScheduler
- Agrega agent/brain_enhanced.py: system prompt mejorado
- Modifica agent/main.py: descomenta lineas 659-662 para testing

Sleep mode comentado para testing - se re-habilitara despues de verificar pricing"

Write-Host ""
Write-Host "OK: Commit creado" -ForegroundColor Green
Write-Host ""

Write-Host "Historial:" -ForegroundColor Cyan
git log --oneline -2

Write-Host ""

# 6. PUSH A GITHUB
Write-Host "[6/6] PUSH a GitHub..." -ForegroundColor Yellow
Write-Host "Ingresa credenciales cuando se pida (token de GitHub)" -ForegroundColor Cyan
Write-Host ""

git push origin main -v

Write-Host ""
Write-Host "================================"
Write-Host "  OK: PUSH COMPLETADO"
Write-Host "================================"
Write-Host ""

Write-Host "Proximos pasos:" -ForegroundColor Cyan
Write-Host "1. Espera 2-3 minutos a que Railway detecte el push"
Write-Host "2. Ve a https://railway.app y verifica nuevo deployment"
Write-Host "3. Prueba en WhatsApp: Cuanto cuesta reparar iPhone 13?"
Write-Host "4. Verifica que recibas precio (no TESTING MODE)"
Write-Host ""

Write-Host "Si Railway no deploya automaticamente:" -ForegroundColor Yellow
Write-Host "git commit --allow-empty -m 'trigger redeploy'"
Write-Host "git push origin main"
Write-Host ""

pause
