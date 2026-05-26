#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para importar citas al calendario
Maneja emojis correctamente (a diferencia de PowerShell)
"""

import requests
import json
from datetime import datetime

URL = "https://tecnology-support-agent-production.up.railway.app/api/calendar/importar-de-texto"

CITAS = [
    "🔔 *NUEVA CITA AGENDADA*\n👤 Jose Luis Gil Miranda | 📱 PS5\n⏰ Sábado 9 de mayo, 11:30 a.m. | ⚠️ Sobrecalentamiento, se apaga sola\n👨‍💼 Asesor: Sofia",

    "🔔 *NUEVA CITA AGENDADA*\n👤 Andrés | 📱 PS5\n⏰ Sábado 16 de mayo, 11:00 a.m. | ⚠️ Consola se apaga después de 30 minutos\n👨‍💼 Asesor: Valentina",

    "🔔 *NUEVA CITA AGENDADA*\n👤 Emmanuel | 📱 PS5\n⏰ Sábado 9 de mayo, 12:00 p.m. | ⚠️ Puerto HDMI con falso contacto\n👨‍💼 Asesor: Camila",

    "🔔 *NUEVA CITA AGENDADA*\n👤 Francisco González | 📱 PS3\n⏰ Jueves 14 de mayo, 7:30 p.m. | ⚠️ Charola no jala los discos\n👨‍💼 Asesor: Sofia",

    "🔔 *NUEVA CITA AGENDADA*\n👤 Gonz | 📱 Xbox Series S\n⏰ Sábado 9 de mayo, 12:30 p.m. | ⚠️ Mantenimiento por sobrecalentamiento\n👨‍💼 Asesor: Sofia",

    "🔔 *NUEVA CITA AGENDADA*\n👤 Augusto | 📱 PS4\n⏰ Sábado 9 de mayo, 5:30 p.m. | ⚠️ Mantenimiento\n👨‍💼 Asesor: Valentina",

    "🔔 *NUEVA CITA AGENDADA*\n👤 Raul Del Prado Flores | 📱 Xbox Series X\n⏰ Sábado 16 de mayo, 11:30 a.m. | ⚠️ Mantenimiento\n👨‍💼 Asesor: Valentina",

    "🔔 *NUEVA CITA AGENDADA*\n👤 José Antonio | 📱 PS5 con lector de discos\n⏰ Sábado 16 de mayo, 1:30 p.m. | ⚠️ Bandeja de discos dañada\n👨‍💼 Asesor: Valentina",

    "🔔 *NUEVA CITA AGENDADA*\n👤 Pablo | 📱 PS5\n⏰ Sábado 16 de mayo, 11:30 a.m. | ⚠️ Se calienta y se apaga\n👨‍💼 Asesor: Sofia",

    "🔔 *NUEVA CITA AGENDADA*\n👤 Eric Soto Rodríguez | 📱 Xbox 360 (x2) + Moto Z\n⏰ Jueves 14 de mayo, 11:00 a.m. | ⚠️ Xbox 360 con falla, Moto Z cambio de pantalla\n👨‍💼 Asesor: Sofia",

    "🔔 *NUEVA CITA AGENDADA*\n👤 Israel | 📱 Nintendo Switch\n⏰ Sábado 16 de mayo, 11:30 a.m. | ⚠️ Drift en palancas\n👨‍💼 Asesor: Sofia",

    "🔔 *NUEVA CITA AGENDADA*\n👤 José Juan Campos Medina | 📱 PS4 Fat, PS3 Fat, Xbox 360\n⏰ Domingo 17 de mayo, 12:00 p.m. | ⚠️ Mantenimiento profundo\n👨‍💼 Asesor: Camila",

    "🔔 *NUEVA CITA AGENDADA*\n👤 Carlos Tengo | 📱 iPhone 14\n⏰ Sábado 16 de mayo, 2:00 p.m. | ⚠️ Centro de carga dañado\n👨‍💼 Asesor: Sofia",

    "🔔 *NUEVA CITA AGENDADA*\n👤 Jaime Escamilla | 📱 Xbox Series X Digital\n⏰ Miércoles 13 de mayo, 10:30 a.m. | ⚠️ Puerto Ethernet fallo\n👨‍💼 Asesor: Camila",

    "🔔 *NUEVA CITA AGENDADA*\n👤 Irving Sanchez | 📱 Xbox One\n⏰ Viernes 15 de mayo, 5:00 p.m. | ⚠️ No enciende\n👨‍💼 Asesor: Sofia",

    "🔔 *NUEVA CITA AGENDADA*\n👤 David | 📱 PS5\n⏰ Sábado 16 de mayo, 2:45 p.m. | ⚠️ Se calienta mucho\n👨‍💼 Asesor: Valentina",

    "🔔 *NUEVA CITA AGENDADA*\n👤 Diego Gutierrez | 📱 Sony PS Vita PCH-1000\n⏰ Sábado 16 de mayo, 12:00 p.m. | ⚠️ Fallo en joystick\n👨‍💼 Asesor: Daniela",
]

def main():
    print("=" * 50)
    print("  IMPORTADOR DE CITAS")
    print("=" * 50)
    print(f"Total de citas a importar: {len(CITAS)}\n")

    payload = {"mensajes": CITAS}
    headers = {"Content-Type": "application/json"}

    try:
        print(f"📤 Enviando solicitud a {URL}...\n")
        response = requests.post(URL, json=payload, headers=headers, timeout=30)
        result = response.json()

        print("✅ RESULTADO:")
        print("=" * 50)
        print(f"✓ Importadas: {result.get('importadas', 0)}")
        print(f"⏭️  Ya existentes: {result.get('ya_existentes', 0)}")
        print(f"❌ Errores: {result.get('errores', 0)}")
        print(f"📊 Total procesadas: {result.get('total_encontradas', 0)}")
        print(f"⏰ Timestamp: {result.get('timestamp', 'N/A')}")
        print("=" * 50)

        if result.get('errores', 0) > 0:
            print("\n🔴 Detalles de errores:")
            for detalle in result.get('detalles', []):
                if detalle.get('estado') == 'error':
                    print(f"  ❌ #{detalle.get('numero')}: {detalle.get('razon', 'Error desconocido')}")

        if result.get('importadas', 0) > 0:
            print("\n✅ Citas importadas exitosamente:")
            for detalle in result.get('detalles', []):
                if detalle.get('estado') == 'importada':
                    print(f"  ✓ #{detalle.get('numero')}: {detalle.get('nombre', '?')}")

    except requests.exceptions.RequestException as e:
        print(f"❌ ERROR en la solicitud: {e}")
    except json.JSONDecodeError:
        print("❌ ERROR: Respuesta inválida del servidor")
    except Exception as e:
        print(f"❌ ERROR inesperado: {e}")

    print("\n" + "=" * 50)
    print("Proceso completado.")

if __name__ == "__main__":
    main()
