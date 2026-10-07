"""Adaptador ASR sobre Groq Cloud API (Whisper).

Solo gestiona comunicación HTTP, serialización y resiliencia. No depende de
torch ni del paquete whisper local.
"""

import logging
import math
from pathlib import Path
from typing import Any

from groq import (
    APIConnectionError,
    APIStatusError,
    BadRequestError,
    Groq,
    RateLimitError,
)

from app.core.config import settings

logger = logging.getLogger(__name__)


def _confidence_from_segments(segments: Any) -> float | None:
    """Convierte avg_logprob de los segmentos en un porcentaje 0-100."""
    if not segments:
        return None

    logprobs: list[float] = []
    for segment in segments:
        value = (
            segment.get("avg_logprob")
            if isinstance(segment, dict)
            else getattr(segment, "avg_logprob", None)
        )
        if isinstance(value, (int, float)):
            logprobs.append(float(value))

    if not logprobs:
        return None

    mean_logprob = sum(logprobs) / len(logprobs)
    return round(min(max(math.exp(mean_logprob), 0.0), 1.0) * 100, 2)


class WhisperAdapter:
    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 2,
    ) -> None:
        self.api_key: str = api_key or settings.groq_api_key
        self.model_name: str = model_name or settings.groq_whisper_model
        self.timeout: float = timeout
        self.max_retries: int = max_retries
        self._client: Groq | None = None

    @property
    def client(self) -> Groq:
        """Crea el cliente bajo demanda para no fallar al importar sin API key."""
        if self._client is None:
            if not self.api_key:
                raise RuntimeError(
                    "El servicio de transcripción no está configurado."
                )
            self._client = Groq(
                api_key=self.api_key,
                timeout=self.timeout,
                max_retries=self.max_retries,
            )
        return self._client

    def transcribe(
        self,
        audio_path: str | Path,
        language: str | None = "es",
        model_name: str | None = None,
    ) -> dict[str, Any]:
        """Transcribe un archivo de audio.

        Retorna ``text``, ``raw_text``, ``language``, ``model_name`` y
        ``confidence`` (porcentaje 0-100 o ``None`` si no hay segmentos).
        """
        path = Path(audio_path)
        if not path.is_file():
            raise FileNotFoundError(f"Archivo de audio no encontrado: {audio_path}")

        effective_model = model_name or self.model_name
        request_args: dict[str, Any] = {
            "model": effective_model,
            "response_format": "verbose_json",
        }
        if language:
            request_args["language"] = language

        try:
            with path.open("rb") as file_handle:
                response = self.client.audio.transcriptions.create(
                    file=(path.name, file_handle),
                    **request_args,
                )
        except BadRequestError as exc:
            logger.error("Audio rechazado por Groq ASR: %s", exc)
            raise RuntimeError("El audio no pudo ser procesado por el servicio de transcripción.") from exc
        except RateLimitError as exc:
            logger.error("Límite de uso de Groq ASR alcanzado: %s", exc)
            raise RuntimeError(
                "El servicio de transcripción está saturado. Intenta nuevamente en unos instantes."
            ) from exc
        except APIConnectionError as exc:
            logger.error("Fallo de conexión o timeout con Groq ASR: %s", exc)
            raise RuntimeError("No se pudo conectar con el servicio de transcripción.") from exc
        except APIStatusError as exc:
            logger.error(
                "Error HTTP %s de Groq ASR: %s", getattr(exc, "status_code", "?"), exc
            )
            raise RuntimeError("El servicio de transcripción devolvió un error.") from exc

        text: str = (getattr(response, "text", None) or "").strip()
        segments = getattr(response, "segments", None)

        return {
            "text": text,
            "raw_text": text,
            "language": language,
            "model_name": effective_model,
            "confidence": _confidence_from_segments(segments),
        }


whisper_adapter = WhisperAdapter()
