#!/usr/bin/env python3
# tests/diagnostico.py — Script de diagnóstico del bot
# Ejecutar con: python tests/diagnostico.py

"""
Diagnóstico completo del bot de WhatsApp.
Verifica cada componente para encontrar dónde están los problemas.
"""

import asyncio
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from agent.memory import inicializar_db, guardar_mensaje, obtener_historial
from agent.brain import generar_respuesta
from agent.providers import obtener_proveedor

load_dotenv()


class Diagnostico:
    def __init__(self):
        self.resultados = []
        self.errores = []

    def log(self, paso: str, resultado: str, estado: str = "✅"):
        """Registra un resultado."""
        linea = f"{estado} {paso}: {resultado}"
        print(linea)
        self.resultados.append(linea)

    def error(self, paso: str, detalle: str):
        """Registra un error."""
        linea = f"❌ {paso}: {detalle}"
        print(linea)
        self.errores.append(linea)

    async def verificar_variables_entorno(self):
        """Paso 1: Verificar variables de entorno"""
        print("\n" + "=" * 60)
        print("PASO 1: Verificar Variables de Entorno")
        print("=" * 60)

        variables_requeridas = {
            "ANTHROPIC_API_KEY": "API de Anthropic",
            "WHATSAPP_PROVIDER": "Proveedor de WhatsApp",
            "DATABASE_URL": "URL de base de datos",
        }

        for var, desc in variables_requeridas.items():
            valor = os.getenv(var)
            if valor:
                # Mostrar solo primeros y últimos caracteres por seguridad
                if len(valor) > 20:
                    valor_display = valor[:8] + "..." + valor[-8:]
                else:
                    valor_display = valor
                self.log(f"Variable {var}", valor_display)
            else:
                self.error(f"Variable {var}", f"NO CONFIGURADA ({desc})")

        # Verificar proveedor específico
        proveedor = os.getenv("WHATSAPP_PROVIDER", "whapi").lower()
        print(f"\n📍 Proveedor elegido: {proveedor}")

        if proveedor == "whapi":
            if os.getenv("WHAPI_TOKEN"):
                self.log("WHAPI_TOKEN", "Configurado ✓")
            else:
                self.error("WHAPI_TOKEN", "NO CONFIGURADO")
        elif proveedor == "meta":
            for var in ["META_ACCESS_TOKEN", "META_PHONE_NUMBER_ID"]:
                if os.getenv(var):
                    self.log(var, "Configurado ✓")
                else:
                    self.error(var, "NO CONFIGURADO")

    async def verificar_bd(self):
        """Paso 2: Verificar base de datos"""
        print("\n" + "=" * 60)
        print("PASO 2: Verificar Base de Datos")
        print("=" * 60)

        try:
            await inicializar_db()
            self.log("Inicialización de BD", "Exitosa")

            # Intentar guardar y recuperar un mensaje de prueba
            telefono_test = "test-diagnostico-001"
            texto_test = f"Mensaje de prueba — {datetime.now().isoformat()}"

            await guardar_mensaje(telefono_test, "user", texto_test)
            self.log("Guardar mensaje", "Exitoso")

            historial = await obtener_historial(telefono_test)
            if historial and historial[-1]["content"] == texto_test:
                self.log("Recuperar mensaje", "Exitoso — datos coinciden ✓")
            else:
                self.error("Recuperar mensaje", "Datos no coinciden o no encontrados")

        except Exception as e:
            self.error("Base de datos", str(e))

    async def verificar_proveedor(self):
        """Paso 3: Verificar proveedor de WhatsApp"""
        print("\n" + "=" * 60)
        print("PASO 3: Verificar Proveedor de WhatsApp")
        print("=" * 60)

        try:
            proveedor = obtener_proveedor()
            self.log("Carga de proveedor", f"{proveedor.__class__.__name__} ✓")

            # Verificar atributos clave
            if hasattr(proveedor, "parsear_webhook"):
                self.log("Método parsear_webhook", "Disponible ✓")
            else:
                self.error("Método parsear_webhook", "NO ENCONTRADO")

            if hasattr(proveedor, "enviar_mensaje"):
                self.log("Método enviar_mensaje", "Disponible ✓")
            else:
                self.error("Método enviar_mensaje", "NO ENCONTRADO")

        except Exception as e:
            self.error("Proveedor", str(e))

    async def verificar_claude_api(self):
        """Paso 4: Verificar conexión con Claude API"""
        print("\n" + "=" * 60)
        print("PASO 4: Verificar Claude API (Anthropic)")
        print("=" * 60)

        try:
            # Intentar generar una respuesta simple
            mensaje_test = "Hola, ¿cuál es tu nombre?"
            historial = []

            self.log("Llamando generar_respuesta", "Iniciado...")
            respuesta = await generar_respuesta(mensaje_test, historial)

            if respuesta and len(respuesta) > 0:
                respuesta_preview = respuesta[:80] + "..." if len(respuesta) > 80 else respuesta
                self.log("Claude API", f"Respuesta generada ✓\n   → '{respuesta_preview}'")
            else:
                self.error("Claude API", "Retornó respuesta vacía")

        except Exception as e:
            self.error("Claude API", str(e))

    async def verificar_flujo_completo(self):
        """Paso 5: Simular flujo completo"""
        print("\n" + "=" * 60)
        print("PASO 5: Simular Flujo Completo")
        print("=" * 60)

        try:
            # Simular un flujo completo
            telefono_test = "test-flujo-completo-001"
            mensaje_usuario = "¿Cuánto cuesta reparar un display de Samsung A55?"

            self.log("1. Guardar mensaje del usuario", "Iniciado...")
            await guardar_mensaje(telefono_test, "user", mensaje_usuario)
            self.log("1. Guardar mensaje del usuario", "Exitoso ✓")

            self.log("2. Obtener historial", "Iniciado...")
            historial = await obtener_historial(telefono_test)
            self.log("2. Obtener historial", f"Exitoso ({len(historial)} mensajes) ✓")

            self.log("3. Generar respuesta", "Iniciado...")
            respuesta = await generar_respuesta(mensaje_usuario, historial)
            self.log("3. Generar respuesta", f"Exitoso ({len(respuesta)} caracteres) ✓")

            self.log("4. Guardar respuesta del bot", "Iniciado...")
            await guardar_mensaje(telefono_test, "assistant", respuesta)
            self.log("4. Guardar respuesta del bot", "Exitoso ✓")

            # Verificar que el historial se actualizó
            historial_actualizado = await obtener_historial(telefono_test)
            if len(historial_actualizado) == len(historial) + 2:
                self.log("5. Verificar historial actualizado", "Exitoso ✓")
            else:
                self.error(
                    "5. Verificar historial",
                    f"Esperaba {len(historial) + 2} mensajes, obtuvo {len(historial_actualizado)}"
                )

        except Exception as e:
            self.error("Flujo completo", str(e))

    async def ejecutar(self):
        """Ejecutar todo el diagnóstico"""
        print("\n")
        print("╔══════════════════════════════════════════════════════════╗")
        print("║        DIAGNÓSTICO DEL BOT DE WHATSAPP — AgentKit         ║")
        print("║                                                          ║")
        print(f"║  Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                         ║")
        print("╚══════════════════════════════════════════════════════════╝")

        try:
            await self.verificar_variables_entorno()
            await self.verificar_bd()
            await self.verificar_proveedor()
            await self.verificar_claude_api()
            await self.verificar_flujo_completo()

        except Exception as e:
            print(f"\n❌ Error fatal durante diagnóstico: {e}")
            import traceback
            traceback.print_exc()

        # Resumen final
        print("\n" + "=" * 60)
        print("RESUMEN DEL DIAGNÓSTICO")
        print("=" * 60)

        if self.errores:
            print(f"\n⚠️  Se encontraron {len(self.errores)} PROBLEMA(S):\n")
            for error in self.errores:
                print(f"  {error}")
        else:
            print("\n✅ ¡TODO ESTÁ FUNCIONANDO CORRECTAMENTE!")

        print(f"\n📋 Total de verificaciones: {len(self.resultados)}")
        print(f"✅ Exitosas: {len(self.resultados) - len(self.errores)}")
        print(f"❌ Fallidas: {len(self.errores)}\n")


async def main():
    diag = Diagnostico()
    await diag.ejecutar()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⏹️  Diagnóstico interrumpido por el usuario.")
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
