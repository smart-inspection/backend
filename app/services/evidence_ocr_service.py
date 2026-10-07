"""
Servicio OCR para evidencias mediante Groq Vision.

Delega la inferencia al adaptador GroqVisionAdapter con tracking de emisiones,
validación de integridad y persistencia en Evidence.
"""

from __future__ import annotations

import gc
import logging
from datetime import datetime, timezone
from pathlib import Path

from PIL import UnidentifiedImageError
from sqlalchemy.orm import Session

from app.core.carbon import track_ai_emissions
from app.db.models import Evidence
from app.integrations.ocr.groq_vision_adapter import groq_vision_adapter
from app.integrations.ocr.preprocessing import validate_image_integrity

logger = logging.getLogger(__name__)


def process_evidence_ocr(db: Session, evidence_id: int) -> Evidence | None:
    """Pipeline OCR sobre evidencia mediante Groq Vision.

    1. Valida existencia y formato de imagen.
    2. Valida integridad del archivo de evidencia.
    3. Extrae texto y confianza con Groq Vision.
    4. Persiste resultados en el modelo Evidence.
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
        validate_image_integrity(absolute_path)
        with track_ai_emissions(task_name="ocr_processing"):
            result = groq_vision_adapter.extract_text(absolute_path)

        extracted_text = result.get("text") or None
        confidence = result.get("confidence")

    except UnidentifiedImageError:
        logger.warning(
            "Imagen corrupta o no reconocida (evidence_id=%s): %s",
            evidence_id, absolute_path,
        )
        extracted_text = None
        confidence = 0.0
    except (OSError, RuntimeError) as exc:
        logger.error(
            "Error procesando Groq Vision OCR (evidence_id=%s): %s",
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