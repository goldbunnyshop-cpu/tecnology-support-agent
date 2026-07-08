# push-fix-cache-prompt.ps1
# Sube SOLO el fix de prompt caching en agent/brain.py
# (separa el system prompt estatico del contexto dinamico para que el cache de
#  Anthropic funcione y se reduzca el costo por mensaje en conversaciones activas)

Set-Location $PSScriptRoot

# Si hay un index.lock viejo de otra sesion/herramienta, lo quitamos primero
if (Test-Path ".git\index.lock") {
    Write-Host "Eliminando .git\index.lock residual..." -ForegroundColor Yellow
    Remove-Item ".git\index.lock" -Force
}

# Mostrar que va a subirse
git status agent/brain.py

git add agent/brain.py

git commit -m "fix: separar system prompt estatico del contexto dinamico para habilitar prompt caching

- El system prompt del asesor (~5700 tokens) se manda completo en cada
  mensaje. Antes el contexto dinamico (fecha/hora, perfil cliente) se
  pegaba ANTES del prompt estatico, lo que rompia el prefijo y el cache
  de Anthropic nunca aplicaba.
- Ahora el system se manda como 2 bloques: el estatico con
  cache_control=ephemeral primero, y el dinamico al final.
- Dentro de la ventana de 5 min, mensajes seguidos de una misma
  conversacion deberian leer ese bloque del cache (~10% del costo
  normal) en vez de pagarlo completo cada vez.
- Se agrega logging de cache_read_input_tokens / cache_creation_input_tokens
  para verificar en produccion."

git push origin main

Write-Host ""
Write-Host "Listo. Revisa los logs de Railway despues del deploy:" -ForegroundColor Green
Write-Host '  Busca lineas tipo: [Sofia] Respuesta generada (X in / Y out | cache: N leidos, M creados)' -ForegroundColor Green
Write-Host "  En el 2do mensaje de una conversacion, 'cache: N leidos' deberia ser > 0." -ForegroundColor Green
