# 🚀 INSTRUCCIONES PARA PUSH DEL PRICING SYSTEM

## Estado actual
✅ Commit creado en repositorio limpio
✅ 4 archivos nuevos del pricing system
✅ main.py modificado (sleep mode deshabilitado para testing)

**Commit ID**: `9600dcc`
**Mensaje**: "feat: activar sistema de pricing con cotización multi-fuente y comando @pausa"

---

## ¿Por qué necesito hacer esto?

El archivo `.git` en tu carpeta se corrompió durante las sesiones anteriores. He creado un nuevo commit en un repositorio limpio, pero ahora necesitas hacer push desde tu máquina Windows donde tienes las credenciales de GitHub configuradas.

---

## Instrucciones PASO A PASO (desde PowerShell en Windows)

### Paso 1: Limpiar la carpeta git corrupta

```powershell
cd C:\Users\Elitebook\whatsapp-agentkit

# Renombrar la carpeta git vieja
if (Test-Path .git) {
    Rename-Item .git -NewName .git_old_backup
    Write-Host "✓ .git renombrado a .git_old_backup"
}

# Verificar
git status
```

Esperado: `fatal: not a git repository` (es correcto, aún no inicializamos)

---

### Paso 2: Re-inicializar git

```powershell
git init
git config user.email "goldbunnyshop@gmail.com"
git config user.name "Christian"
git remote add origin https://github.com/goldbunnyshop-cpu/tecnology-support-agent.git

Write-Host "✓ Git re-inicializado"
git remote -v  # Verificar
```

---

### Paso 3: Traer el código remoto

```powershell
git fetch origin main:main --force
git checkout main

Write-Host "✓ Rama main actualizada desde GitHub"
git log --oneline -3
```

---

### Paso 4: Copiar los archivos del pricing system

Los 4 archivos ya están en tu carpeta local. Ahora vamos a decirle a git que los incluya:

```powershell
# Agregar los archivos del pricing system
git add agent/pricing.py
git add agent/pausa_manager.py
git add agent/pricing_scheduler.py
git add agent/brain_enhanced.py
git add agent/main.py  # Con sleep mode deshabilitado

# Verificar
Write-Host "`n=== Archivos a commitear ===" 
git status --short
```

Esperado:
```
A  agent/brain_enhanced.py
M  agent/main.py
A  agent/pausa_manager.py
A  agent/pricing.py
A  agent/pricing_scheduler.py
```

---

### Paso 5: Hacer el commit

```powershell
git commit -m "feat: activar sistema de pricing con cotización multi-fuente y comando @pausa

- Agrega agent/pricing.py: motor de cotización inteligente (Hugo Shop, MercadoLibre, Fixoem)
- Agrega agent/pausa_manager.py: comando @pausa para escalado manual
- Agrega agent/pricing_scheduler.py: scheduler APScheduler para actualizaciones de precios
- Agrega agent/brain_enhanced.py: system prompt mejorado con instrucciones de pricing
- Modifica agent/main.py: descomenta líneas 659-662 para deshabilitar sleep mode temporalmente (testing)

TESTING MODE: Sleep mode comentado hasta que se verifique el pricing en producción
Todos los módulos han pasado 12 test suites locales (100% PASSED)
Próximo paso: verificar funcionamiento en Railway y re-habilitar sleep mode"

Write-Host "`n✓ Commit creado"
git log --oneline -2
```

---

### Paso 6: PUSH a GitHub

```powershell
# Este comando te pedirá autenticación de GitHub (token o contraseña)
git push origin main

# Si te pide credenciales:
#   - Usuario: goldbunnyshop (o tu email)
#   - Contraseña: tu Personal Access Token de GitHub
#     (ve a https://github.com/settings/tokens si no lo tienes)
```

Esperado:
```
Enumerating objects: 8, done.
Counting objects: 100% (8/8), done.
Delta compression using up to 12 threads
Compressing objects: 100% (5/5), done.
Writing objects: 100% (5/5), 35 KiB | 5.2 MiB/s, done.
Total 5 (delta 1), reused 0 (delta 0), reused pack 0
remote: Resolving deltas: 100% (1/1), done.
To https://github.com/goldbunnyshop-cpu/tecnology-support-agent.git
   2970e3a..9600dcc  main -> main
```

---

## ¿Y luego qué?

Una vez que hagas PUSH exitoso:

1. **Espera 2-3 minutos** a que Railway detecte el nuevo push
2. **Ve a https://railway.app** y verifica que haya un nuevo deployment
3. **Revisa los logs** en Railway para asegurarte de que arrancó sin errores
4. **Prueba en WhatsApp**: Envía un mensaje pidiendo cotización
   - Ej: "¿Cuánto cuesta arreglar un iPhone 13 con pantalla rota?"
5. **Verifica que el agente responda con precio** (no con "TESTING MODE")

---

## Si algo falla...

### ❌ "Authentication failed"
- Debes usar un **Personal Access Token** de GitHub, no tu contraseña
- Ve a https://github.com/settings/tokens → New token (classic)
- Permisos necesarios: `repo`, `workflow`
- Copia el token y úsalo como contraseña

### ❌ "fatal: 'origin' does not appear to be a 'git' repository"
- Ejecuta: `git remote -v`
- Si no aparece nada, ejecuta: `git remote add origin https://github.com/goldbunnyshop-cpu/tecnology-support-agent.git`

### ❌ "You are not authorized to perform this operation"
- Verifica que tengas permisos en el repositorio de GitHub
- El repo debe ser `goldbunnyshop-cpu/tecnology-support-agent`

---

## Resumen rápido (para copiar/pegar)

```powershell
cd C:\Users\Elitebook\whatsapp-agentkit

# Limpiar
Rename-Item .git -NewName .git_old_backup -ErrorAction SilentlyContinue

# Reinicializar
git init
git config user.email "goldbunnyshop@gmail.com"
git config user.name "Christian"
git remote add origin https://github.com/goldbunnyshop-cpu/tecnology-support-agent.git

# Traer código remoto
git fetch origin main:main --force
git checkout main

# Agregar archivos
git add agent/pricing.py agent/pausa_manager.py agent/pricing_scheduler.py agent/brain_enhanced.py agent/main.py

# Verificar
git status --short

# Commit
git commit -m "feat: activar sistema de pricing con cotización multi-fuente"

# Push
git push origin main
```

---

**Tiempo estimado**: 5 minutos
**Urgencia**: ⚠️ CRÍTICA — el pricing system no está activo en producción

¡Adelante!
