import requests
import json

BASE_URL = "http://127.0.0.1:8000"

# Test 1: Cotización simple
print("\n" + "="*60)
print("TEST 1: COTIZACIÓN SIMPLE")
print("="*60)

payload = {
    "telefono": "5551234567",
    "texto": "¿Cuánto cuesta cambiar la pantalla de un Samsung Galaxy A12?",
    "nombre_cliente": "Test User",
    "asesor": "Christian"
}

try:
    response = requests.post(f"{BASE_URL}/webhook", json=payload, timeout=10)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")

# Test 2: Incertidumbre (debe pausar)
print("\n" + "="*60)
print("TEST 2: INCERTIDUMBRE - DEBE PAUSAR")
print("="*60)

payload2 = {
    "telefono": "5551234567",
    "texto": "Tengo un Xiaomi pero no sé si es OLED o AMOLED",
    "nombre_cliente": "Test User",
    "asesor": "Christian"
}

try:
    response = requests.post(f"{BASE_URL}/webhook", json=payload2, timeout=10)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")

print("\n✓ Tests completados")