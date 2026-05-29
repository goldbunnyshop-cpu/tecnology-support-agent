# RUNBOOK_OPERACION_DIARIA.md

## 1) Objetivo
Guia rapida para operar el agente de WhatsApp en produccion (Railway + Whapi + Google Calendar).

## 2) Estado saludable (check diario de 2 minutos)
1. Railway servicio en `Running`.
2. Endpoint responde:
   - `GET /` -> 200 con `{"status":"ok"}`
   - `GET /webhook` -> 200
3. Logs sin errores repetitivos de:
   - `HttpError 404 ... calendars/... Not Found`
   - `WHAPI_TOKEN no configurado`
   - `ANTHROPIC_API_KEY` invalida
4. Prueba funcional:
   - Mensaje de WhatsApp de prueba -> respuesta < 10s.

## 3) Variables criticas (Railway)
- `WHATSAPP_PROVIDER=whapi`
- `WHAPI_TOKEN=...`
- `ANTHROPIC_API_KEY=...`
- `GOOGLE_CREDENTIALS_JSON=...`
- `GOOGLE_CALENDAR_ID=...@group.calendar.google.com`
- `ENVIRONMENT=production`
- `GRUPO_CHRISTIAN_INTERNO=...@g.us`
- `NUMERO_EXCEPCION_PRUEBAS=5627557362`

## 4) Flujo de citas esperado
1. Cliente pide cita.
2. Bot ofrece horarios disponibles.
3. Cliente confirma horario.
4. Bot agenda en Google Calendar.
5. Bot confirma al cliente.
6. Bot notifica al grupo interno.

Si falla calendar:
- Debe verse en logs `HttpError` y el sistema hace confirmacion manual/fallback.

## 5) Incidencias comunes y solucion rapida

### A) No responde mensajes
- Revisar logs: entrada `POST /webhook`.
- Si no hay entradas, revisar URL en Whapi:
  - `https://<app>.up.railway.app/webhook`
- Si hay entradas pero no respuesta:
  - validar `WHAPI_TOKEN` y `ANTHROPIC_API_KEY`.

### B) No agenda en Google Calendar
- Revisar `GOOGLE_CALENDAR_ID` (ID completo, no recortado).
- Verificar calendario compartido con el `client_email` de la Service Account.
- Permiso minimo: `Realizar cambios en los eventos`.

### C) Error SMTP `Network is unreachable`
- No bloquea WhatsApp ni Calendar.
- Afecta solo notificacion por email.
- Mantener notificacion por grupo como canal principal.

### D) Sleep mode responde cuando no debe (o viceversa)
- Confirmar horario 00:00-06:00.
- Numero de pruebas en excepcion:
  - `NUMERO_EXCEPCION_PRUEBAS=5627557362`

## 6) Checklist antes de cada deploy
1. `git status` limpio (o cambios intencionales).
2. Commit con mensaje claro.
3. Push a rama conectada a Railway (`main`).
4. Verificar deployment `SUCCESS`.
5. Probar:
   - `GET /`
   - mensaje de WhatsApp real
   - cita de prueba (si hubo cambios de calendar)

## 7) Comandos utiles (PowerShell)
```powershell
cd C:\Users\Elitebook\whatsapp-agentkit
git status
git add .
git commit -m "chore: update"
git push origin main
```

Validacion local:
```powershell
python -m compileall agent
python -m uvicorn agent.main:app --host 127.0.0.1 --port 8080 --reload
```

## 8) Politica de seguridad recomendada
1. No pegar keys completas en chats/documentos.
2. Rotar credenciales de Service Account si hubo exposicion accidental.
3. Guardar secretos solo en Railway Variables.
4. Revisar accesos compartidos de Google Calendar cada mes.

## 9) Escalamiento
Escalar inmediatamente si ocurre alguno:
- 5+ minutos sin respuestas del bot.
- Errores 500 repetitivos en webhook.
- `HttpError 403/404` persistente en Calendar.
- Sospecha de compromiso de credenciales.

---
Ultima actualizacion: 2026-05-28
