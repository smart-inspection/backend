"""
Servicio OCR alternativo basado en Tesseract para evidencias.

Delega la normalización de imagen al pipeline centralizado
en ``app.integrations.ocr.preprocessing``.
"""

from __future__ import annotations

import gc
import logging
from datetime import datetime, timezone
from pathlib import Path

import pytesseract
from PIL import Image, UnidentifiedImageError
from pytesseract import Output
from sqlalchemy.orm import Session

from app.db.models import Evidence
from app.integrations.ocr.preprocessing import (
    normalize_image,
    validate_image_integrity,
)

logger = logging.getLogger(__name__)

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def _extract_text_and_confidence(image: Image.Image) -> tuple[str | None, float | None]:
    """Ejecuta Tesseract sobre una imagen PIL ya normalizada."""
    data = pytesseract.image_to_data(
        image, output_type=Output.DICT, config="--oem 3 --psm 6",
    )

    words: list[str] = []
    confidences: list[float] = []

    for text, conf in zip(data["text"], data["conf"]):
        clean_text = (text or "").strip()
        try:
            conf_value = float(conf)
        except (TypeError, ValueError):
            conf_value = -1

        if clean_text:
            words.append(clean_text)

        if conf_value >= 0:
            confidences.append(conf_value)

    extracted_text = " ".join(words).strip() or None
    avg_confidence = (
        round(sum(confidences) / len(confidences), 2) if confidences else None
    )

    return extracted_text, avg_confidence


def process_evidence_ocr(db: Session, evidence_id: int) -> Evidence | None:
    """Pipeline Tesseract con validación defensiva de imagen.

    1. Valida integridad del archivo.
    2. Normaliza con el pipeline centralizado (EXIF, RGB, downscale 1920 px).
    3. Ejecuta Tesseract.
    4. Persiste resultados.

    Si la imagen está corrupta o es ilegible, registra ``confidence=0``
    sin romper la ejecución del servidor.
    """
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not evidence:
        return None

    if not evidence.file_type.startswith("image/"):
        raise ValueError("El OCR solo está habilitado para imágenes")

    absolute_path = Path.cwd() / evidence.file_path
    if not absolute_path.exists():
        raise ValueError("No se encontró el archivo de la evidencia")

    try:
        # Validar integridad antes de procesar
        validate_image_integrity(absolute_path)

        # Normalizar con pipeline centralizado (devuelve PIL.Image en memoria)
        image = normalize_image(
            absolute_path,
            max_side=1920,
            apply_sharpen=True,
            convert_grayscale=True,
        )

        extracted_text, confidence = _extract_text_and_confidence(image)

    except UnidentifiedImageError:
        logger.warning(
            "Imagen corrupta o no reconocida (evidence_id=%s): %s",
            evidence_id, absolute_path,
        )
        extracted_text = None
        confidence = 0.0
    except (OSError, RuntimeError) as exc:
        logger.error(
            "Error procesando Tesseract OCR (evidence_id=%s): %s",
            evidence_id, exc,
        )
        extracted_text = None
        confidence = 0.0
    finally:
        gc.collect()

    evidence.ocr_extracted_text = extracted_text
    evidence.ocr_confidence = confidence
    evidence.ocr_processed = True
    evidence.ocr_last_processed_at = datetime.now(timezone.utc)

    db.add(evidence)
    db.commit()
    db.refresh(evidence)
    return evidence