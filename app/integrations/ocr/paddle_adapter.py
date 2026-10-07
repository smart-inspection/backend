"""
Adaptador de compatibilidad para PaddleOCR.

Delega la inferencia al servicio Groq Vision para evitar dependencias
locales pesadas de deep learning.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.integrations.ocr.groq_vision_adapter import groq_vision_adapter

logger = logging.getLogger(__name__)


def get_paddle_engine() -> Any:
    """Función de compatibilidad retroactiva."""
    return None


def collect_texts_and_scores(
    node: Any,
    texts: list[str],
    scores: list[float],
) -> None:
    """Función de compatibilidad retroactiva."""
    pass


def extract_with_paddle(image_path: Path) -> tuple[str, float | None]:
    """Delega la extracción de texto a Groq Vision."""
    result = groq_vision_adapter.extract_text(image_path)
    return result.get("text", "") or "", result.get("confidence")
