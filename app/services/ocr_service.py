"""
Servicio OCR — orquesta preprocesamiento, extracción y persistencia.

Delega la normalización de imagen a ``app.integrations.ocr.preprocessing``
y la inferencia PaddleOCR a ``app.integrations.ocr.paddle_adapter``.
"""

import gc
import logging
import os

os.environ["PADDLE_PDX_DISABLE_MKLDNN"] = "1"
os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["FLAGS_use_onednn"] = "0"
os.environ["FLAGS_enable_pir_api"] = "0"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

from datetime import datetime, timezone
from pathlib import Path

from PIL import UnidentifiedImageError
from sqlalchemy.orm import Session

from app.db.models import Evidence
from app.integrations.ocr.paddle_adapter import (
    collect_texts_and_scores,
    extract_with_paddle,
    get_paddle_engine,
)
from app.integrations.ocr.preprocessing import (
    normalize_and_save,
    validate_image_integrity,
)

from app.core.carbon import track_ai_emissions

logger = logging.getLogger(__name__)


# ── Re-exportaciones (compatibilidad con validation_service) ──
# validation_service.py importa: extract_text_from_evidence_record
# ocr.py importa:               extract_text_from_evidence
# Ambas funciones se mantienen aquí con la misma firma.


# ── Utilidades ────────────────────────────────────────────────

def resolve_file_path(file_path: str) -> Path:
    """Resuelve la ruta absoluta de un archivo de evidencia."""
    raw_path = Path(file_path)

    candidates = [
        raw_path,
        Path.cwd() / file_path.lstrip("/"),
        Path.cwd()
        / "uploads"
        / file_path.lstrip("/").replace("uploads/", "").replace("uploads\\", ""),
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()

    raise FileNotFoundError(f"archivo no encontrado para OCR: {file_path}")


# ── Preprocesamiento ─────────────────────────────────────────

def preprocess_image(image_path: Path) -> Path:
    """Normaliza la imagen (EXIF, RGB, downscale a 1920 px, sharpen)
    y la guarda como archivo temporal ``*_paddle_preprocessed.png``.

    Delega al pipeline centralizado en ``preprocessing.py``.
    """
    return normalize_and_save(
        image_path,
        max_side=1920,
        suffix="_paddle_preprocessed.png",
    )


# ── Extracción ────────────────────────────────────────────────

def extract_text_and_confidence(image_path: Path) -> tuple[str, float | None]:
    """Ejecuta PaddleOCR sobre la imagen preprocesada.

    Delega al adaptador optimizado en ``paddle_adapter.py``.
    """
    with track_ai_emissions(task_name="ocr_processing"):
        return extract_with_paddle(image_path)



# ── Orquestación sobre Evidence ──────────────────────────────

def extract_text_from_evidence_record(db: Session, evidence: Evidence) -> dict:
    """Procesa OCR sobre un registro de evidencia existente.

    Pipeline:
    1. Validar integridad del archivo.
    2. Preprocesar (normalizar, downscale).
    3. Ejecutar PaddleOCR.
    4. Persistir resultados en el registro ORM.
    5. Limpiar archivo preprocesado temporal.
    """
    if not evidence.file_type.lower().startswith("image"):
        raise ValueError("solo se permite OCR sobre evidencias de imagen")

    image_path = resolve_file_path(evidence.file_path)
    processed_path: Path | None = None

    try:
        # 1. Validar integridad
        validate_image_integrity(image_path)

        # 2. Preprocesar
        processed_path = preprocess_image(image_path)

        # 3. Extraer texto
        extracted_text, confidence = extract_text_and_confidence(processed_path)

    except UnidentifiedImageError:
        logger.warning(
            "Imagen corrupta o no reconocida (evidence_id=%s): %s",
            evidence.id, image_path,
        )
        extracted_text = ""
        confidence = 0.0
    except (OSError, RuntimeError) as exc:
        logger.error(
            "Error procesando OCR (evidence_id=%s): %s",
            evidence.id, exc,
        )
        extracted_text = ""
        confidence = 0.0
    finally:
        # 5. Limpiar archivo temporal
        if processed_path and processed_path.exists():
            try:
                processed_path.unlink()
            except OSError:
                pass
        gc.collect()

    # 4. Persistir resultados
    evidence.ocr_extracted_text = extracted_text
    evidence.ocr_confidence = confidence
    evidence.ocr_processed = True
    evidence.ocr_last_processed_at = datetime.now(timezone.utc)

    db.add(evidence)
    db.commit()
    db.refresh(evidence)

    return {
        "evidence_id": evidence.id,
        "evidence_category": evidence.evidence_category,
        "file_path": str(image_path),
        "extracted_text": evidence.ocr_extracted_text or "",
        "confidence": float(evidence.ocr_confidence) if evidence.ocr_confidence is not None else None,
    }


def extract_text_from_evidence(db: Session, evidence_id: int) -> dict | None:
    """Busca la evidencia por ID y delega al pipeline OCR completo."""
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not evidence:
        return None

    return extract_text_from_evidence_record(db, evidence)

def process_evidence_ocr(evidence_id: int, image_path: str) -> str:
    """Función de compatibilidad para procesar OCR sobre una ruta de imagen."""
    text, _ = extract_text_and_confidence(Path(image_path))
    return text