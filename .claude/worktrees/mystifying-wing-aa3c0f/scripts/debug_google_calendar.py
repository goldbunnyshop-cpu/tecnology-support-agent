#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de diagnóstico para Google Calendar.

Responde a la pregunta: ¿por qué la cita "se crea exitosamente" pero no aparece
en mi Google Calendar personal?

Lo que hace:
1. Muestra el client_email REAL del archivo de credenciales (detecta typos).
2. Lista TODOS los calendarios a los que tiene acceso la Service Account.
3. Lee el GOOGLE_CALENDAR_ID configurado en .env.
4. Crea un evento de prueba y muestra el organizer/creator devuelto por la API
   — eso revela en QUÉ calendario terminó.
5. Borra el evento de prueba.

Uso:
    python scripts/debug_google_calendar.py
"""

import os
import sys
import json
from datetime import datetime, timedelta

# Permitir ejecutar desde la raíz del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/calendar"]
CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "config/credentials.json")
CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "primary")


def banner(texto: str):
    print("\n" + "=" * 70)
    print(f"   {texto}")
    print("=" * 70)


def paso_1_credenciales():
    banner("PASO 1: Inspeccionar archivo de credenciales")
    print(f"Ruta configurada: {CREDENTIALS_PATH}")

    if not os.path.exists(CREDENTIALS_PATH):
        print(f"ERROR: el archivo NO existe.")
        return None

    with open(CREDENTIALS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    client_email = data.get("client_email", "(no encontrado)")
    project_id = data.get("project_id", "(no encontrado)")
    tipo = data.get("type", "(no encontrado)")

    print(f"Tipo de credencial: {tipo}")
    print(f"Project ID:         {project_id}")
    print(f"Client email (SA):  {client_email}")
    print()
    print("IMPORTANTE: Este es el email EXACTO que debes usar al compartir tu")
    print("calendario personal en calendar.google.com. Verifica que coincida")
    print("letra por letra con lo que vas a pegar — un solo typo y no funciona.")

    return client_email


def paso_2_listar_calendarios():
    banner("PASO 2: Listar calendarios accesibles por la Service Account")

    creds = Credentials.from_service_account_file(CREDENTIALS_PATH, scopes=SCOPES)
    service = build("calendar", "v3", credentials=creds)

    resp = service.calendarList().list().execute()
    items = resp.get("items", [])

    if not items:
        print("La Service Account NO tiene calendarios visibles.")
        print("Eso significa que tu calendario personal NO está compartido con ella.")
        print()
        print("Solución: ve a calendar.google.com → ajustes del calendario →")
        print("'Compartir con personas específicas' → agrega el client_email del paso 1")
        print("→ permiso 'Hacer cambios en eventos'.")
        return service, []

    print(f"Encontrados {len(items)} calendarios:\n")
    for cal in items:
        print(f"  • summary:    {cal.get('summary', '?')}")
        print(f"    id:         {cal.get('id', '?')}")
        print(f"    accessRole: {cal.get('accessRole', '?')}")
        print(f"    primary:    {cal.get('primary', False)}")
        print()

    return service, items


def paso_3_resolver_calendar_id(service, calendarios_visibles):
    banner("PASO 3: Validar GOOGLE_CALENDAR_ID configurado")
    print(f"Valor en .env: GOOGLE_CALENDAR_ID = {CALENDAR_ID!r}")
    print()

    if CALENDAR_ID == "primary":
        print("ADVERTENCIA: 'primary' apunta al calendario de la propia Service")
        print("Account, NO al tuyo. Los eventos se crean en un calendario que")
        print("nadie puede ver desde calendar.google.com.")
        print()
        print("Cambia GOOGLE_CALENDAR_ID en .env por tu email de Google,")
        print("p.ej. GOOGLE_CALENDAR_ID=goldbunnyshop@gmail.com")
        return False

    coincide = any(c.get("id") == CALENDAR_ID for c in calendarios_visibles)
    if coincide:
        print(f"OK: la Service Account tiene acceso a {CALENDAR_ID}")
        return True

    print(f"ERROR: la Service Account NO ve {CALENDAR_ID} en su lista.")
    print("Probablemente aún no compartiste el calendario con ella, o lo")
    print("compartiste con un email distinto al del paso 1.")
    return False


def paso_4_evento_de_prueba(service):
    banner("PASO 4: Crear evento de prueba para ver dónde aterriza")

    ahora = datetime.now()
    inicio = (ahora + timedelta(minutes=10)).replace(microsecond=0, second=0)
    fin = inicio + timedelta(minutes=15)

    evento = {
        "summary": "AgentKit — Evento de prueba (debug)",
        "description": "Evento creado por scripts/debug_google_calendar.py. Se borra solo.",
        "start": {"dateTime": inicio.isoformat(), "timeZone": "America/Mexico_City"},
        "end":   {"dateTime": fin.isoformat(),    "timeZone": "America/Mexico_City"},
    }

    print(f"Insertando en calendarId = {CALENDAR_ID!r}")
    try:
        creado = service.events().insert(calendarId=CALENDAR_ID, body=evento).execute()
    except HttpError as e:
        print(f"ERROR HTTP de la API: {e}")
        print()
        print("404 = el calendarId no existe o no tienes permiso.")
        print("403 = la Service Account no tiene permiso de escritura.")
        return

    print()
    print("Evento creado. Respuesta cruda de la API:")
    print(f"  id:        {creado.get('id')}")
    print(f"  status:    {creado.get('status')}")
    print(f"  htmlLink:  {creado.get('htmlLink')}")
    print(f"  creator:   {creado.get('creator')}")
    print(f"  organizer: {creado.get('organizer')}")
    print()
    print(">>> Mira 'organizer.email' — ESE es el calendario donde realmente")
    print(">>> aterrizó el evento. Si NO es tu email personal, el problema")
    print(">>> es el GOOGLE_CALENDAR_ID, no las credenciales.")
    print()

    # Limpieza
    try:
        service.events().delete(calendarId=CALENDAR_ID, eventId=creado["id"]).execute()
        print("Evento de prueba borrado.")
    except Exception as e:
        print(f"No pude borrar el evento de prueba: {e}")
        print(f"Bórralo manualmente: id = {creado['id']}")


def main():
    client_email = paso_1_credenciales()
    if not client_email:
        return

    service, calendarios = paso_2_listar_calendarios()
    if service is None:
        return

    paso_3_resolver_calendar_id(service, calendarios)
    paso_4_evento_de_prueba(service)

    banner("RESUMEN")
    print("1. Comparte tu calendario personal con el client_email del paso 1.")
    print("2. Pon GOOGLE_CALENDAR_ID=<tu email de Google> en .env.")
    print("3. Vuelve a correr este script. 'organizer' debe ser tu email.")


if __name__ == "__main__":
    main()
