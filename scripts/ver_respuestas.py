import sqlite3
import json
from datetime import datetime, timedelta

# Conectar a la base de datos
conn = sqlite3.connect('./agentkit.db')
cursor = conn.cursor()

print("\n" + "="*70)
print("ÚLTIMOS MENSAJES PROCESADOS")
print("="*70)

# Obtener últimos 10 mensajes
cursor.execute("""
    SELECT telefono, rol, contenido, timestamp 
    FROM mensajes 
    ORDER BY timestamp DESC 
    LIMIT 10
""")

mensajes = cursor.fetchall()
for tel, rol, contenido, ts in mensajes:
    print(f"\n📱 {tel} | {rol.upper()} | {ts}")
    print(f"   {contenido[:150]}...")

print("\n" + "="*70)
print("PAUSAS ACTIVAS")
print("="*70)

cursor.execute("""
    SELECT cliente_telefono, fecha_pausa, duracion_minutos, razon, activa
    FROM pausas
    ORDER BY fecha_pausa DESC
    LIMIT 5
""")

pausas = cursor.fetchall()
if pausas:
    for tel, fecha, duracion, razon, activa in pausas:
        estado = "🟢 ACTIVA" if activa else "🔴 Resuelta"
        print(f"\n{estado} | {tel}")
        print(f"   Inicio: {fecha} | Duración: {duracion} min")
        print(f"   Razón: {razon}")
else:
    print("Sin pausas registradas")

conn.close()
print("\n")