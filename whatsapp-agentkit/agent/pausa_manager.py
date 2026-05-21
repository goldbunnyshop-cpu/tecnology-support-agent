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
    """Gestor de comando @pausa para escalar a intervención humana"""

    # Patrones para detectar comando pausa
    PATRON_PAUSA = r'@pausa:\s*(\d+)'
    PATRON_PAUSA_ALTERNATIVO = r'pausa\s*[:\-]\s*(\d+)'

    def __init__(self):
        self.pausas_activas = {}  # {numero: timestamp}
        self.historial_pausas = []  # Log de todas las pausas

    @staticmethod
    def detectar_comando_pausa(texto: str) -> Optional[str]:
        """Detecta comando @pausa en texto

        Args:
            texto: Texto de la respuesta de Claude

        Returns:
            Número telefónico si se detecta pausa, None si no
        """
        # Buscar @pausa: {NÚMERO}
        match = re.search(PausaManager.PATRON_PAUSA, texto)
        if match:
            numero = match.group(1).strip()
            return numero

        # Fallback: buscar "pausa: {NÚMERO}" sin @
        match = re.search(PausaManager.PATRON_PAUSA_ALTERNATIVO, texto)
        if match:
            numero = match.group(1).strip()
            return numero

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
            # Aquí se integraría con agent.memory.pausar_conversacion
            # await pausar_conversacion(numero_limpio, horas=duracion_horas)

            # Registrar pausa local
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
    """Procesa respuesta de Claude para detectar y ejecutar comando pausa"""

    def __init__(self, pausa_manager: PausaManager):
        self.pausa_manager = pausa_manager

    async def procesar(
        self,
        respuesta_claude: str,
        numero_cliente: str,
        asesor: str = "Sofia"
    ) -> Tuple[str, bool]:
        """Procesa respuesta detectando comandos pausa

        Args:
            respuesta_claude: Respuesta generada por Claude
            numero_cliente: Número del cliente
            asesor: Nombre del asesor

        Returns:
            (respuesta_limpia: str, pausa_ejecutada: bool)
        """
        # Detectar comando pausa
        numero_pausa = PausaManager.detectar_comando_pausa(respuesta_claude)

        if numero_pausa:
            logger.info(f"[PAUSA-PROCESADOR] Pausa detectada en respuesta de {asesor}")

            # Ejecutar pausa
            exito, mensaje = await self.pausa_manager.procesar_pausa(
                numero_pausa,
                razon="Consulta técnica requiere especialista",
                duracion_horas=2
            )

            if exito:
                # Remover comando de respuesta antes de enviar al cliente
                respuesta_limpia = re.sub(
                    PausaManager.PATRON_PAUSA,
                    "",
                    respuesta_claude
                )
                respuesta_limpia = respuesta_limpia.strip()

                logger.info(f"[PAUSA-PROCESADOR] Comando removido de respuesta al cliente")

                return respuesta_limpia, True
            else:
                logger.error(f"[PAUSA-PROCESADOR] Error ejecutando pausa: {mensaje}")
                return respuesta_claude, False
        else:
            # No hay comando pausa, retornar respuesta sin cambios
            return respuesta_claude, False


# ====================================================================
# INSTRUCCIONES PARA CLAUDE (inyectar en system prompt)
# ====================================================================

INSTRUCCIONES_PAUSA = """

### 🛑 COMANDO DE PAUSA PARA ESCALADO

Cuando necesites que un técnico especialista atienda directamente al cliente:

**FORMATO:**
Escribe exactamente: `@pausa: {NÚMERO_CLIENTE}`

**EJEMPLOS:**
- `@pausa: 5541234567`
- `@pausa: 555 412 3456`
- `@pausa: 55-5141-2345`

**EL COMANDO SERÁ PROCESADO AUTOMÁTICAMENTE - NO APARECERÁ EN EL MENSAJE AL CLIENTE**

**CASOS PARA ACTIVAR PAUSA:**

1. **Incertidumbre técnica**: No estás seguro del tipo de pantalla (OLED vs AMOLED)
   - Ejemplo: Cliente no sabe especificar, y tú tienes dudas
   - Respuesta: "Le comunicamos con un técnico especializado. @pausa: 5541234567"

2. **Dispositivo no catalogado**: Modelo que no está en sistema
   - Ejemplo: Marca/modelo muy nuevo o muy antiguo
   - Respuesta: "Este modelo requiere evaluación directa. @pausa: 5541234567"

3. **Gama alta con solicitud especial**: Cliente con iPhone/Pixel/Galaxy S solicita garantía
   - Respuesta: "Te paso con especialista para detalles de garantía. @pausa: 5541234567"

4. **Cliente quiere negociar precio**: Cliente solicita descuento o términos especiales
   - Respuesta: "Déjame consultar disponibilidad de promociones. @pausa: 5541234567"

5. **Solicitud fuera de scope**: Reparación de algo no soportado
   - Respuesta: "Eso requiere evaluación especializada. @pausa: 5541234567"

6. **Cliente en duda o confundido**: Múltiples preguntas contradictorias sobre especificaciones
   - Respuesta: "Es mejor que hables directamente con nuestro técnico. @pausa: 5541234567"

**PROTOCOLO POST-PAUSA:**
1. El comando se ejecuta automáticamente
2. Christian recibe notificación en grupo WhatsApp
3. Conversación se pausa para que Christian responda directamente
4. Cuando Christian termine, él reanuda la conversación

**IMPORTANCIA:**
- ✅ Mejor overescalar que cotizar mal
- ✅ La pausa es señal de calidad, no de incompetencia
- ✅ Christian prefiere manejar casos complejos desde el inicio
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
