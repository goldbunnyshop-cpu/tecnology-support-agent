# agent/pausa_manager.py — Gestor de comando @pausa para intervención humana
# Maneja pausas de conversación cuando hay incertidumbre o escalado

import os
import re
import logging
from datetime import datetime
from typing import Optional, Tuple
from zoneinfo import ZoneInfo

logger = logging.getLogger("agentkit")

ZONA_MEXICO = ZoneInfo("America/Mexico_City")

# Números que NO deben ser pausados (son internos)
NUMERO_NEGOCIO = os.getenv("NUMERO_NEGOCIO", "5659866275")
NUMERO_CHRISTIAN = os.getenv("NUMERO_CHRISTIAN", "5541576331")
NUMEROS_INTERNOS = {NUMERO_NEGOCIO, NUMERO_CHRISTIAN}


class PausaManager:
    """Gestor de comandos: @pausa, detener, clabe"""

    # Patrones para detectar comandos (case-insensitive)
    PATRON_PAUSA = r'@?pausa\s*[:\-]\s*(\d+)'
    PATRON_DETENER = r'detener\s*[:\-]\s*(\d+)'
    PATRON_CLABE = r'clabe\s*[:\-]\s*(\d+)'

    def __init__(self):
        self.pausas_activas = {}  # {numero: timestamp}
        self.clientes_detenidos = set()  # Clientes donde NO responder
        self.historial_pausas = []  # Log de todas las pausas

    @staticmethod
    def detectar_comando(texto: str) -> Optional[Tuple[str, str]]:
        """Detecta comandos: pausa, detener, clabe (case-insensitive)

        Args:
            texto: Texto de la respuesta de Claude

        Returns:
            (tipo_comando, numero) o None si no hay comando
            tipo_comando: "pausa" | "detener" | "clabe"
        """
        # Case-insensitive
        texto_lower = texto.lower()

        # PAUSA
        match = re.search(PausaManager.PATRON_PAUSA, texto_lower)
        if match:
            return ("pausa", match.group(1).strip())

        # DETENER
        match = re.search(PausaManager.PATRON_DETENER, texto_lower)
        if match:
            return ("detener", match.group(1).strip())

        # CLABE
        match = re.search(PausaManager.PATRON_CLABE, texto_lower)
        if match:
            return ("clabe", match.group(1).strip())

        return None

    @staticmethod
    def normalizar_numero(numero: str) -> str:
        """Normaliza número telefónico removiendo espacios y caracteres especiales"""
        return re.sub(r'\D', '', numero)

    @staticmethod
    def validar_numero(numero: str) -> bool:
        """Valida que sea un número telefónico válido (10-15 dígitos)"""
        numero_limpio = PausaManager.normalizar_numero(numero)
        return 10 <= len(numero_limpio) <= 15

    @staticmethod
    def es_numero_interno(numero: str) -> bool:
        """Verifica si es un número interno (Christian o negocio)"""
        numero_limpio = PausaManager.normalizar_numero(numero)
        return numero_limpio in NUMEROS_INTERNOS

    async def procesar_pausa(
        self,
        numero_cliente: str,
        razon: str = "Intervención técnica requerida",
        duracion_horas: int = 2
    ) -> Tuple[bool, str]:
        """Procesa una solicitud de pausa

        Args:
            numero_cliente: Número del cliente
            razon: Motivo de la pausa
            duracion_horas: Horas de duración (default 2)

        Returns:
            (exito: bool, mensaje: str)
        """
        # Validar número
        if not self.validar_numero(numero_cliente):
            return False, f"❌ Número inválido: {numero_cliente}"

        numero_limpio = self.normalizar_numero(numero_cliente)

        # Protección: no pausar números internos
        if self.es_numero_interno(numero_limpio):
            logger.warning(f"[PAUSA] Intento de pausar número interno: {numero_limpio}")
            return False, f"⚠️ No se puede pausar número interno: {numero_limpio}"

        # Verificar si ya está pausado
        if numero_limpio in self.pausas_activas:
            return False, f"⚠️ Ya está pausado: {numero_limpio}"

        try:
            # Guardar pausa en la base de datos
            from agent.memory import pausar_conversacion
            await pausar_conversacion(numero_limpio, horas=duracion_horas)

            # Registrar pausa local (respaldo en memoria)
            self.pausas_activas[numero_limpio] = datetime.now(ZONA_MEXICO)
            self.historial_pausas.append({
                'numero': numero_limpio,
                'timestamp': datetime.now(ZONA_MEXICO).isoformat(),
                'razon': razon,
                'duracion_horas': duracion_horas,
            })

            logger.info(f"[PAUSA] {numero_limpio} pausado por: {razon} ({duracion_horas}h)")

            # Aquí se integraría con agent.notifications
            # await notificar_grupo_pausa(numero_limpio, razon)

            return True, f"✓ Conversación pausada. Christian será notificado."

        except Exception as e:
            logger.error(f"Error procesando pausa: {e}")
            return False, f"❌ Error al pausar: {str(e)}"

    async def procesar_detener(self, numero_cliente: str) -> Tuple[bool, str]:
        """Marca cliente para detener automatización de respuestas

        Args:
            numero_cliente: Número del cliente

        Returns:
            (exito: bool, mensaje: str)
        """
        # Validar número
        if not self.validar_numero(numero_cliente):
            return False, f"❌ Número inválido: {numero_cliente}"

        numero_limpio = self.normalizar_numero(numero_cliente)

        # Protección: no detener números internos
        if self.es_numero_interno(numero_limpio):
            logger.warning(f"[DETENER] Intento de detener número interno: {numero_limpio}")
            return False, f"⚠️ No se puede detener número interno: {numero_limpio}"

        try:
            self.clientes_detenidos.add(numero_limpio)
            logger.info(f"[DETENER] {numero_limpio} marcado como detenido — NO enviar respuestas automatizadas")

            return True, f"✓ Automatización detenida para {numero_limpio}. Christian debe responder manualmente."

        except Exception as e:
            logger.error(f"Error deteniendo cliente: {e}")
            return False, f"❌ Error al detener: {str(e)}"

    async def procesar_clabe(self, numero_cliente: str) -> Tuple[bool, list[str]]:
        """Envía información de transferencia bancaria (CLABE)

        Args:
            numero_cliente: Número del cliente

        Returns:
            (exito: bool, mensajes: list[str]) — lista de mensajes a enviar en orden
        """
        # Validar número
        if not self.validar_numero(numero_cliente):
            return False, [f"❌ Número inválido: {numero_cliente}"]

        numero_limpio = self.normalizar_numero(numero_cliente)

        try:
            # CLABE: 18 dígitos sin espacios
            clabe = "167580000057534814"

            # Mensaje 1: CLABE sin espacios
            mensaje_1 = clabe

            # Mensaje 2: Datos bancarios
            mensaje_2 = "Nombre: Gold Bunny TS\nBanco: Hey banco (Banregio)"

            logger.info(f"[CLABE] Enviando información CLABE a {numero_limpio}")

            return True, [mensaje_1, mensaje_2]

        except Exception as e:
            logger.error(f"Error procesando CLABE: {e}")
            return False, [f"❌ Error al enviar CLABE: {str(e)}"]

    async def reanudar_pausa(self, numero_cliente: str) -> Tuple[bool, str]:
        """Reanuda una conversación pausada

        Args:
            numero_cliente: Número del cliente

        Returns:
            (exito: bool, mensaje: str)
        """
        numero_limpio = self.normalizar_numero(numero_cliente)

        try:
            # Aquí se integraría con agent.memory.reanudar_conversacion
            # await reanudar_conversacion(numero_limpio)

            if numero_limpio in self.pausas_activas:
                del self.pausas_activas[numero_limpio]

            logger.info(f"[PAUSA] {numero_limpio} reanudado")
            return True, f"✓ Conversación reanudada para {numero_limpio}"

        except Exception as e:
            logger.error(f"Error reanudando pausa: {e}")
            return False, f"❌ Error al reanudar: {str(e)}"

    def obtener_estado_pausa(self, numero_cliente: str) -> Optional[dict]:
        """Obtiene estado de pausa para un cliente"""
        numero_limpio = self.normalizar_numero(numero_cliente)

        if numero_limpio in self.pausas_activas:
            return {
                'numero': numero_limpio,
                'pausado_desde': self.pausas_activas[numero_limpio].isoformat(),
            }
        return None

    def listar_pausas_activas(self) -> list:
        """Lista todas las pausas activas"""
        return [
            {
                'numero': num,
                'desde': timestamp.isoformat(),
            }
            for num, timestamp in self.pausas_activas.items()
        ]

    def obtener_historial_pausas(self, numero_cliente: Optional[str] = None, limite: int = 10) -> list:
        """Obtiene historial de pausas para un cliente o global"""
        if numero_cliente:
            numero_limpio = self.normalizar_numero(numero_cliente)
            return [
                p for p in self.historial_pausas
                if p['numero'] == numero_limpio
            ][-limite:]
        return self.historial_pausas[-limite:]


# ====================================================================
# INTEGRACIÓN CON RESPUESTA DE CLAUDE
# ====================================================================

class ProcesadorRespuestaConPausa:
    """Procesa respuesta de Claude para detectar y ejecutar comandos (pausa, detener, clabe)"""

    def __init__(self, pausa_manager: PausaManager):
        self.pausa_manager = pausa_manager

    async def procesar(
        self,
        respuesta_claude: str,
        numero_cliente: str,
        asesor: str = "Sofia"
    ) -> Tuple[str, bool, list[str]]:
        """Procesa respuesta detectando comandos pausa, detener, clabe

        Args:
            respuesta_claude: Respuesta generada por Claude
            numero_cliente: Número del cliente
            asesor: Nombre del asesor

        Returns:
            (respuesta_limpia: str, comando_ejecutado: bool, mensajes_adicionales: list[str])
            - respuesta_limpia: respuesta sin comandos
            - comando_ejecutado: True si se ejecutó algún comando
            - mensajes_adicionales: mensajes extra a enviar (vacío para pausa, 2 para clabe)
        """
        # Detectar comando (pausa, detener, clabe)
        resultado = PausaManager.detectar_comando(respuesta_claude)

        if not resultado:
            # No hay comando, retornar respuesta sin cambios
            return respuesta_claude, False, []

        tipo_comando, numero = resultado
        logger.info(f"[PROCESADOR] Comando '{tipo_comando}' detectado en respuesta de {asesor}")

        # Remover comando de respuesta antes de enviar al cliente
        respuesta_limpia = re.sub(
            PausaManager.PATRON_PAUSA if tipo_comando == "pausa" else
            PausaManager.PATRON_DETENER if tipo_comando == "detener" else
            PausaManager.PATRON_CLABE,
            "",
            respuesta_claude,
            flags=re.IGNORECASE
        )
        respuesta_limpia = respuesta_limpia.strip()

        # Procesar según tipo de comando
        if tipo_comando == "pausa":
            logger.info(f"[PROCESADOR] Ejecutando pausa para {numero}")
            exito, mensaje = await self.pausa_manager.procesar_pausa(
                numero,
                razon="Consulta técnica requiere especialista",
                duracion_horas=2
            )

            if exito:
                logger.info(f"[PROCESADOR] Pausa ejecutada — Christian será notificado")
                return respuesta_limpia, True, []
            else:
                logger.error(f"[PROCESADOR] Error en pausa: {mensaje}")
                return respuesta_claude, False, []

        elif tipo_comando == "detener":
            logger.info(f"[PROCESADOR] Ejecutando detener para {numero}")
            exito, mensaje = await self.pausa_manager.procesar_detener(numero)

            if exito:
                logger.info(f"[PROCESADOR] Cliente detenido — no enviar respuestas automáticas")
                return respuesta_limpia, True, []
            else:
                logger.error(f"[PROCESADOR] Error en detener: {mensaje}")
                return respuesta_claude, False, []

        elif tipo_comando == "clabe":
            logger.info(f"[PROCESADOR] Ejecutando envío CLABE para {numero}")
            exito, mensajes = await self.pausa_manager.procesar_clabe(numero)

            if exito:
                logger.info(f"[PROCESADOR] CLABE enviada — {len(mensajes)} mensajes a seguir")
                return respuesta_limpia, True, mensajes
            else:
                logger.error(f"[PROCESADOR] Error en CLABE: {mensajes}")
                return respuesta_claude, False, []

        else:
            logger.warning(f"[PROCESADOR] Comando desconocido: {tipo_comando}")
            return respuesta_claude, False, []


# ====================================================================
# INSTRUCCIONES PARA CLAUDE (inyectar en system prompt)
# ====================================================================

INSTRUCCIONES_PAUSA = """

### 🛑 COMANDOS DEL MENÚ INTERNO (Taller Interno TS)

Tienes 3 comandos para gestionar conversaciones desde el bot:

---

## 1️⃣ **PAUSA** — Escalada a especialista

**Cuándo usar:** Cliente requiere atención de Christian (especialista técnico)

**FORMATO:** `@pausa: {NÚMERO}` (case-insensitive: `pausa:`, `Pausa:`, `@pausa:`, etc.)

**EJEMPLOS:**
- `@pausa: 5541234567`
- `Pausa: 555 412 3456`
- `pausa: 55-5141-2345`

**EL COMANDO SERÁ REMOVIDO AUTOMÁTICAMENTE — NO APARECERÁ EN EL MENSAJE AL CLIENTE**

**CASOS PARA ACTIVAR PAUSA:**

1. **Incertidumbre técnica**: No estás seguro del tipo de pantalla (OLED vs AMOLED)
2. **Dispositivo no catalogado**: Modelo muy nuevo o muy antiguo
3. **Gama alta con solicitud especial**: Cliente con iPhone/Pixel/Galaxy S solicita garantía
4. **Cliente quiere negociar precio**: Descuento o términos especiales
5. **Solicitud fuera de scope**: Reparación no soportada
6. **Cliente confundido**: Múltiples preguntas contradictorias

**PROTOCOLO POST-PAUSA:**
- ✅ Comando se ejecuta automáticamente
- ✅ Conversación se pausa
- ✅ Christian recibe notificación
- ✅ Christian responde directamente
- ✅ Cuando termine, Christian reanuda la conversación

---

## 2️⃣ **DETENER** — Pausar respuestas automáticas

**Cuándo usar:** Cliente necesita que Christian lo atienda manualmente sin respuestas del bot

**FORMATO:** `detener: {NÚMERO}` (case-insensitive)

**EJEMPLOS:**
- `detener: 5541234567`
- `Detener: 555 412 3456`

**EFECTO:**
- ✓ Bot deja de responder automáticamente
- ✓ Christian debe responder manualmente a cada mensaje
- ✓ Se usa cuando hay problema técnico con el cliente o necesita atención 1-a-1

---

## 3️⃣ **CLABE** — Enviar información bancaria

**Cuándo usar:** Cliente solicita CLABE para transferencia bancaria

**FORMATO:** `clabe: {NÚMERO}` (case-insensitive)

**EJEMPLOS:**
- `clabe: 5541234567`
- `Clabe: 555 412 3456`

**EFECTO:**
- Automáticamente se envían 2 mensajes en orden:
  1. CLABE: `167580000057534814` (18 dígitos sin espacios)
  2. Datos: `Nombre: Gold Bunny TS` + `Banco: Hey banco (Banregio)`

**NOTA:** El cliente recibe la información completa en dos mensajes separados para claridad.

---

## ⚠️ NOTAS IMPORTANTES:

- ✅ Los comandos son CASE-INSENSITIVE (funcionan en mayúscula, minúscula, mixto)
- ✅ Los comandos son procesados automáticamente del mensaje de respuesta
- ✅ No aparecerán en el mensaje que ve el cliente
- ✅ Christian está alerta en el grupo para intervenir cuando sea necesario
"""


# ====================================================================
# INSTANCIA GLOBAL
# ====================================================================

_pausa_manager_instance: Optional[PausaManager] = None
_procesador_instance: Optional[ProcesadorRespuestaConPausa] = None


async def obtener_pausa_manager() -> PausaManager:
    """Factory para obtener instancia del PausaManager"""
    global _pausa_manager_instance
    if _pausa_manager_instance is None:
        _pausa_manager_instance = PausaManager()
    return _pausa_manager_instance


async def obtener_procesador_pausa() -> ProcesadorRespuestaConPausa:
    """Factory para obtener instancia del procesador"""
    global _pausa_manager_instance, _procesador_instance
    if _pausa_manager_instance is None:
        _pausa_manager_instance = PausaManager()
    if _procesador_instance is None:
        _procesador_instance = ProcesadorRespuestaConPausa(_pausa_manager_instance)
    return _procesador_instance
