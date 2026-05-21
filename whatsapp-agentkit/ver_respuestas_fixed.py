import sqlite3

conn = sqlite3.connect('./agentkit.db')
cursor = conn.cursor()

print("\n" + "="*70)
print("ÚLTIMOS MENSAJES (últimas 24 horas)")
print("="*70)

# Obtener últimos mensajes
cursor.execute("""
    SELECT telefono, role, content, timestamp 
    FROM mensajes 
    ORDER BY timestamp DESC 
    LIMIT 20
""")

mensajes = cursor.fetchall()
if mensajes:
    for tel, role, content, ts in mensajes:
        print(f"\n📱 {tel} | {role.upper():10} | {ts}")
        print(f"   {content[:120]}...")
else:
    print("Sin mensajes")

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

# Buscar específicamente el número de prueba
print("\n" + "="*70)
print("BÚSQUEDA: Número de prueba 5551234567")
print("="*70)

cursor.execute("""
    SELECT telefono, role, content, timestamp 
    FROM mensajes 
    WHERE telefono = '5551234567'
    ORDER BY timestamp DESC
""")

test_msgs = cursor.fetchall()
if test_msgs:
    print(f"Encontrados {len(test_msgs)} mensajes")
    for tel, role, content, ts in test_msgs:
        print(f"\n{role.upper()} | {ts}: {content}")
else:
    print("❌ NO se encontraron mensajes del número de prueba")
    print("⚠️ Los tests NO se guardaron en la base de datos")

conn.close()