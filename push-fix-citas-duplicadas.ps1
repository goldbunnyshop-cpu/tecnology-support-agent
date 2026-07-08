# push-fix-citas-duplicadas.ps1
# Sube el fix de notificaciones de citas duplicadas en el grupo "Taller Interno TS"
# (agent/appointment_notifications.py)

Set-Location $PSScriptRoot

if (Test-Path ".git\index.lock") {
    Write-Host "Eliminando .git\index.lock residual..." -ForegroundColor Yellow
    Remove-Item ".git\index.lock" -Force
}

git status agent/appointment_notifications.py

git add agent/appointment_notifications.py

git commit -m "fix: evita confirmaciones de cita duplicadas en grupo interno

Causa mas probable de las citas duplicadas/triplicadas en 'Taller Interno TS':

- _enviar_grupo() reintentaba (hasta 3 veces) tambien cuando Whapi
  no respondia a tiempo (timeout) o habia un error de red. Pero en esos
  casos el mensaje puede haberse entregado igual del lado de Whapi, y al
  reintentar se enviaba la MISMA confirmacion otra vez al grupo. Ahora
  solo se reintenta si Whapi responde con un error HTTP explicito
  (la solicitud no se proceso); ante timeout/excepcion ya NO se reintenta.

- notificar_nueva_cita() y notificar_recordatorio_1h() registraban la
  notificacion en citas_notificadas DESPUES de enviarla. Si el scheduler
  de citas-Ulises (corre cada 10 min) se ejecutaba mientras ese envio
  seguia en curso, no encontraba el registro todavia y volvia a notificar
  la misma cita. Ahora se reserva el evento en citas_notificadas ANTES
  de enviar, y si ya esta reservado/enviado se omite el envio."

git push origin main

Write-Host ""
Write-Host "Listo. Para confirmar:" -ForegroundColor Green
Write-Host "  1. Agenda una cita de prueba por WhatsApp." -ForegroundColor Green
Write-Host "  2. El grupo 'Taller Interno TS' debe recibir UNA sola confirmacion." -ForegroundColor Green
Write-Host "  3. Revisa logs de Railway por '[CITAS NOTIF]' y '[CITAS GRUPO]' para confirmar." -ForegroundColor Green
