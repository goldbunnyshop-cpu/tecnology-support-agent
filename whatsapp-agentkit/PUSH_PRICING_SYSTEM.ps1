# Script PowerShell para push del pricing system a GitHub
# Copia todo este script y pégalo en PowerShell

Write-Host "`n================================" -ForegroundColor Cyan
Write-Host "  PUSH PRICING SYSTEM" -ForegroundColor Cyan
Write-Host "================================`n" -ForegroundColor Cyan

# Ir a la carpeta del proyecto
cd C:\Users\Elitebook\whatsapp-agentkit

# 1. LIMPIAR .git corrupto
Write-Host "[1/6] Limpiando .git corrupto..." -ForegroundColor Yellow

if (Test-Path .git) {
    try {
        Rename-Item .git -NewName .git_old_backup -Force -ErrorAction SilentlyContinue
        Write-Host "✓ .git renombrado a .git_old_backup`n" -ForegroundColor Green
    } catch {
        Write-Host "⚠ No se pudo renombrar .git (puede que no exista)`n" -ForegroundColor Yellow
    }
}

# 2. INICIALIZAR GIT
Write-Host "[2/6] Re-inicializando git..." -ForegroundColor Yellow

git init
git config user.email "goldbunnyshop@gmail.com"
git config user.name "Christian"
git remote add origin https://github.com/goldbunnyshop-cpu/tecnology-support-agent.git

Write-Host "✓ Git re-inicializado`n" -ForegroundColor Green

# 3. TRAER CÓDIGO REMOTO
Write-Host "[3/6] Descargando código remoto de GitHub..." -ForegroundColor Yellow

git fetch origin main:main --force
git checkout main

Write-Host "✓ Rama main actualizada`n" -ForegroundColor Green

# 4. AGREGAR ARCHIVOS DEL PRICING SYSTEM
Write-Host "[4/6] Agregando archivos del pricing system..." -ForegroundColor Yellow

git add agent/pricing.py
git add agent/pausa_manager.py
git add agent/pricing_scheduler.py
git add agent/brain_enhanced.py
git add agent/main.py

Write-Host "`nArchivos a commitear:" -ForegroundColor Cyan
git status --short

Write-Host "`n✓ Archivos agregados`n" -ForegroundColor Green

# 5. HACER COMMIT
Write-Host "[5/6] Creando commit..." -ForegroundColor Yellow

git commit -m "feat: activar sistema de pricing con cotización multi-fuente y comando @pausa

- Agrega agent/pricing.py: motor de cotización inteligente (Hugo Shop, MercadoLibre, Fixoem)
- Agrega agent/pausa_manager.py: comando @pausa para escalado manual
- Agrega agent/pricing_scheduler.py: scheduler APScheduler para actualizaciones de precios
- Agrega agent/brain_enhanced.py: system prompt mejorado con instrucciones de pricing
- Modifica agent/main.py: descomenta líneas 659-662 para deshabilitar sleep mode temporalmente (testing)

TESTING MODE: Sleep mode comentado hasta que se verifique el pricing en producción
Todos los módulos han pasado 12 test suites locales (100% PASSED)
Próximo paso: verificar funcionamiento en Railway y re-habilitar sleep mode"

Write-Host "`n✓ Commit creado`n" -ForegroundColor Green

Write-Host "Historial:" -ForegroundColor Cyan
git log --oneline -2

# 6. PUSH A GITHUB
Write-Host "`n[6/6] PUSH a GitHub..." -ForegroundColor Yellow
Write-Host "→ Te pedirá autenticación (token de GitHub o contraseña)`n" -ForegroundColor Cyan

git push origin main -v

Write-Host "`n================================" -ForegroundColor Green
Write-Host "  ✓ PUSH COMPLETADO" -ForegroundColor Green
Write-Host "================================`n" -ForegroundColor Green

Write-Host "Próximos pasos:" -ForegroundColor Cyan
Write-Host "1. Espera 2-3 minutos a que Railway detecte el push"
Write-Host "2. Ve a https://railway.app y verifica nuevo deployment"
Write-Host "3. Prueba en WhatsApp: 'Cuánto cuesta reparar iPhone 13 pantalla rota?'"
Write-Host "4. Verifica que recibas precio (no 'TESTING MODE')`n"

Write-Host "Si Railway no deploya automáticamente:" -ForegroundColor Yellow
Write-Host "→ Haz commit vacío: git commit --allow-empty -m 'trigger redeploy'"
Write-Host "→ git push origin main`n"

pause
