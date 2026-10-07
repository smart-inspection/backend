import base64
import logging
import mimetypes
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


class GroqVisionAdapter:
    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        timeout: float = 45.0,
        max_retries: int = 2,
    ) -> None:
        self.api_key: str = api_key or settings.groq_api_key
        self.model_name: str = model_name or settings.groq_vision_model
        self.timeout: float = timeout
        self.max_retries: int = max_retries
        self._client: Groq | None = None

    @property
    def client(self) -> Groq:
        if self._client is None:
            if not self.api_key:
                raise RuntimeError("GROQ_API_KEY no está configurada para el servicio de visión.")
            self._client = Groq(
                api_key=self.api_key,
                timeout=self.timeout,
                max_retries=self.max_retries,
            )
        return self._client

    def _encode_image(self, image_path: Path) -> tuple[str, str]:
        mime_type, _ = mimetypes.guess_type(str(image_path))
        if not mime_type or not mime_type.startswith("image/"):
            mime_type = "image/jpeg"
        b64_data = base64.b64encode(image_path.read_bytes()).decode("utf-8")
        return b64_data, mime_type

    def extract_text(
        self,
        image_path: str | Path,
        prompt: str = "Extract all text, numbers, license plates, VIN codes, and markings visible in this image verbatim. Return only the extracted text without introductory phrases.",
    ) -> dict[str, Any]:
        path = Path(image_path)
        if not path.is_file():
            raise FileNotFoundError(f"Archivo de imagen no encontrado: {image_path}")

        b64_data, mime_type = self._encode_image(path)
        data_uri = f"data:{mime_type};base64,{b64_data}"

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": data_uri},
                    },
                ],
            }
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.1,
                max_tokens=1024,
            )
        except (BadRequestError, RateLimitError, APIConnectionError, APIStatusError) as exc:
            logger.error("Error en Groq Vision OCR: %s", exc, exc_info=True)
            raise RuntimeError("Fallo en el servicio de extracción OCR en la nube.") from exc

        extracted_text = (response.choices[0].message.content or "").strip()
        confidence = 0.95 if extracted_text else 0.0

        return {
            "text": extracted_text,
            "raw_text": extracted_text,
            "confidence": confidence,
            "engine": "groq_vision_qwen",
        }


groq_vision_adapter = GroqVisionAdapter()
