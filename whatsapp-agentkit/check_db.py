import sqlite3

conn = sqlite3.connect('./agentkit.db')
cursor = conn.cursor()

# Ver estructura de la tabla mensajes
print("Columnas en tabla mensajes:")
cursor.execute("PRAGMA table_info(mensajes)")
columnas = cursor.fetchall()

for col in columnas:
    print(f"  - {col[1]} ({col[2]})")

# Ver últimos 3 mensajes
print("\nÚltimos 3 mensajes:")
cursor.execute('SELECT * FROM mensajes ORDER BY rowid DESC LIMIT 3')
for row in cursor.fetchall():
    print(row)

conn.close()