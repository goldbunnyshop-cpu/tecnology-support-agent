# Google Calendar Integration — Setup

Tu agente de WhatsApp puede sincronizar citas automáticamente con Google Calendar.
Cada cita que se agenda en WhatsApp aparecerá en tu calendario.

---

## **PASO 1: Crear cuenta de servicio en Google Cloud**

### 1.1 Ve a Google Cloud Console
- Abre: https://console.cloud.google.com/
- Si no tienes cuenta, crea una gratis

### 1.2 Crea un nuevo proyecto
```
1. Click en el selector de proyectos (arriba, donde dice "Select a project")
2. Click en "NEW PROJECT"
3. Nombre: AgentKit Calendar
4. Click: CREATE
5. Espera 30 segundos a que se cree
```

### 1.3 Habilita Google Calendar API
```
1. En el buscador (arriba), escribe: "Google Calendar API"
2. Click en el resultado
3. Click en el botón azul: ENABLE
4. Espera a que cargue (puedes ver el progreso)
```

### 1.4 Crea una Cuenta de Servicio
```
1. Ve a: https://console.cloud.google.com/iam-admin/serviceaccounts
2. Click: CREATE SERVICE ACCOUNT
3. Service account name: agentkit-calendar
4. Click: CREATE AND CONTINUE
5. En los siguientes pasos, simplemente haz click en "CONTINUE" o "DONE"
   (No necesitas agregar roles especiales)
```

---

## **PASO 2: Genera la clave JSON**

### 2.1 Ve a la Cuenta de Servicio
```
1. Abre: https://console.cloud.google.com/iam-admin/serviceaccounts
2. Haz click en la cuenta "agentkit-calendar"
```

### 2.2 Crea una clave
```
1. Ve al tab: KEYS
2. Click: ADD KEY → Create new key
3. Type: JSON
4. Click: CREATE
5. Se descargará un archivo: agentkit-calendar-*.json
```

### 2.3 Copia el archivo
```
1. Abre el archivo que se descargó
2. Cópialo completo (Ctrl+A, Ctrl+C)
3. Crea un archivo en tu proyecto: config/credentials.json
4. Pega el contenido completo (Ctrl+V)
5. Guarda el archivo
```

**IMPORTANTE:** Este archivo tiene tus credenciales privadas.
- ✅ Nunca lo subas a GitHub (ya está en .gitignore)
- ✅ Mantenlo seguro en tu máquina

---

## **PASO 3: Comparte tu Google Calendar**

### 3.1 Encuentra el email de la Cuenta de Servicio
```
1. Abre el archivo config/credentials.json que acabas de copiar
2. Busca la línea: "client_email"
3. Copia el email (se ve así: agentkit-calendar@...)
```

### 3.2 Comparte tu Google Calendar
```
1. Abre tu Google Calendar: https://calendar.google.com/
2. Click en tu calendario (en la izquierda, "Mis calendarios" → click en los 3 puntos)
3. Click: Settings and sharing
4. Scroll down hasta "Share with specific people or groups"
5. Click: ADD PEOPLE
6. Pega el email de la Cuenta de Servicio (paso 3.1)
7. Dale permiso: Make changes to events
8. Click: SHARE
```

---

## **PASO 4: Configura tu .env**

Abre tu archivo `.env` y asegúrate de tener:

```env
# Google Calendar
GOOGLE_CREDENTIALS_PATH=config/credentials.json
GOOGLE_CALENDAR_ID=primary
```

Si usas un calendario específico en lugar de PRIMARY, puedes cambiar GOOGLE_CALENDAR_ID al ID del calendario.

---

## **PASO 5: Test la conexión**

Ejecuta este script para verificar que todo funciona:

```bash
python agent/google_calendar_sync.py
```

Deberías ver:
```
✅ Credenciales de Google Calendar cargadas exitosamente
✅ Conexión exitosa — X calendarios encontrados:
   • Mi calendario
   ...
```

Si ves errores, revisa que:
- ✅ El archivo `config/credentials.json` existe
- ✅ El contenido JSON es válido (sin caracteres cortados)
- ✅ Compartiste tu calendario con el email de la Cuenta de Servicio
- ✅ GOOGLE_CALENDAR_API está habilitado en Google Cloud

---

## **PASO 6: Deploy a Railway**

Una vez que funciona localmente:

1. **Crea una carpeta privada en Railway para las credenciales:**
   - Sube el archivo `config/credentials.json` a Railway
   - O colócalo en el volumen persistente de Railway

2. **En Railway → Variables de entorno:**
   ```
   GOOGLE_CREDENTIALS_PATH=config/credentials.json
   GOOGLE_CALENDAR_ID=primary
   ```

3. **Deploy y prueba:**
   ```bash
   git add config/credentials.json.example (NO subas el real)
   git push
   ```

---

## **¿Qué pasa después?**

Una vez configurado, cada vez que alguien agende una cita por WhatsApp:

1. ✅ Se guarda en tu BD (SQLite/PostgreSQL)
2. ✅ Se notifica al grupo "Taller Interno TS"
3. ✅ **Se agrega automáticamente a tu Google Calendar**
4. ✅ Tu equipo ve la cita en tiempo real (si comparten calendario)

---

## **Troubleshooting**

### ❌ "Invalid credentials" o "File not found"
- Verifica que `config/credentials.json` existe
- Abre el archivo y verifica que sea JSON válido

### ❌ "Permission denied"
- Vuelve a compartir tu calendario con el email de la Cuenta de Servicio
- Dale permiso: "Make changes to events"

### ❌ "Calendar not found"
- Usa `GOOGLE_CALENDAR_ID=primary` (tu calendario principal)
- No uses emails como ID de calendario

### ❌ La cita no aparece en el calendario
- Verifica los logs de Railway: `docker compose logs -f`
- Busca líneas que digan `[CALENDAR]`

---

**¿Necesitas ayuda?** Lee los logs de tu servidor:
```bash
# Local:
tail -f logs/agentkit.log

# Railway:
docker compose logs -f agent
```
