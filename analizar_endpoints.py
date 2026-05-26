import re

# Leer main.py
with open('agent/main.py', 'r', encoding='utf-8') as f:
    contenido = f.read()

print("="*70)
print("ENDPOINTS EN main.py")
print("="*70)

# Buscar decoradores @app
endpoints = re.findall(r'@app\.(post|get|put|delete)\s*\(\s*["\']([^"\']+)["\']', contenido)

if endpoints:
    for metodo, ruta in endpoints:
        print(f"  {metodo.upper():6} /{ruta}")
else:
    print("❌ No se encontraron endpoints")

print("\n" + "="*70)
print("BÚSQUEDA: Modo reposo (sleep mode)")
print("="*70)

if "reposo" in contenido.lower() or "sleep" in contenido.lower():
    print("✓ Se encontró lógica de modo reposo")
    
    # Buscar líneas con reposo/sleep
    for i, line in enumerate(contenido.split('\n'), 1):
        if 'reposo' in line.lower() or ('sleep' in line.lower() and 'import' not in line.lower()):
            print(f"  Línea {i}: {line.strip()[:80]}")
else:
    print("No se encontró referencia a modo reposo")

print("\n" + "="*70)
print("BÚSQUEDA: Validación de hora en webhook")
print("="*70)

if "00:00" in contenido or "hour" in contenido or "datetime.now" in contenido:
    print("✓ Se encontró validación de horarios")
    for i, line in enumerate(contenido.split('\n'), 1):
        if ('hour' in line.lower() or '00:00' in line or 'datetime.now' in line) and i > 500 and i < 1000:
            print(f"  Línea {i}: {line.strip()[:80]}")