"""Adaptador LLM sobre Groq Cloud API.

Solo gestiona comunicación HTTP, serialización y resiliencia. No contiene
lógica de negocio ni depende de librerías de inferencia local.
"""

import json
import logging
from typing import Any, TypeVar

from groq import (
    APIConnectionError,
    APIStatusError,
    BadRequestError,
    Groq,
    RateLimitError,
)
from pydantic import BaseModel, ValidationError

from app.core.config import settings

logger = logging.getLogger(__name__)

SchemaT = TypeVar("SchemaT", bound=BaseModel)

_DEFAULT_MAX_TOKENS = 2048


class LLaMAAdapter:
    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        temperature: float | None = None,
        timeout: float = 30.0,
        max_retries: int = 2,
    ) -> None:
        self.api_key: str = api_key or settings.groq_api_key
        self.model_name: str = model_name or settings.groq_llm_model
        self.temperature: float = (
            temperature if temperature is not None else settings.llm_temperature
        )
        self.timeout: float = timeout
        self.max_retries: int = max_retries
        self._client: Groq | None = None

    @property
    def client(self) -> Groq:
        """Crea el cliente bajo demanda para no fallar al importar sin API key."""
        if self._client is None:
            if not self.api_key:
                raise RuntimeError(
                    "El servicio de generación de texto no está configurado."
                )
            self._client = Groq(
                api_key=self.api_key,
                timeout=self.timeout,
                max_retries=self.max_retries,
            )
        return self._client

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Devuelve el texto generado. kwargs: max_tokens, temperature, response_format."""
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        request_args: dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens": kwargs.get("max_tokens", _DEFAULT_MAX_TOKENS),
        }
        if kwargs.get("response_format") is not None:
            request_args["response_format"] = kwargs["response_format"]

        try:
            response = self.client.chat.completions.create(**request_args)
        except BadRequestError as exc:
            logger.error("Solicitud LLM rechazada por Groq: %s", exc)
            raise RuntimeError("La solicitud al servicio de IA no es válida.") from exc
        except RateLimitError as exc:
            logger.error("Límite de uso de Groq LLM alcanzado: %s", exc)
            raise RuntimeError(
                "El servicio de IA está saturado. Intenta nuevamente en unos instantes."
            ) from exc
        except APIConnectionError as exc:
            logger.error("Fallo de conexión o timeout con Groq LLM: %s", exc)
            raise RuntimeError("No se pudo conectar con el servicio de IA.") from exc
        except APIStatusError as exc:
            logger.error(
                "Error HTTP %s de Groq LLM: %s", getattr(exc, "status_code", "?"), exc
            )
            raise RuntimeError("El servicio de IA devolvió un error.") from exc

        if not response.choices:
            logger.error("Groq LLM devolvió una respuesta sin choices.")
            raise RuntimeError("El servicio de IA devolvió una respuesta vacía.")

        return response.choices[0].message.content or ""

    def generate_structured(
        self,
        prompt: str,
        schema: type[SchemaT],
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> SchemaT:
        """Genera una salida validada contra un modelo Pydantic (JSON estructurado)."""
        response_format: dict[str, Any] = {
            "type": "json_schema",
            "json_schema": {
                "name": schema.__name__,
                "schema": schema.model_json_schema(),
            },
        }
        raw_text = self.generate(
            prompt,
            system_prompt=system_prompt,
            response_format=response_format,
            **kwargs,
        )

        try:
            return schema.model_validate(json.loads(raw_text))
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.error("Salida estructurada inválida del LLM: %s", exc)
            raise RuntimeError(
                "El servicio de IA devolvió una respuesta con formato inválido."
            ) from exc


llama_adapter = LLaMAAdapter()
