from pathlib import Path
from datetime import datetime

import pytesseract
from PIL import Image, ImageOps, ImageFilter
from pytesseract import Output
from sqlalchemy.orm import Session

from app.db.models import Evidence


TESSERACT_CONFIG = "--oem 3 --psm 6"


def _resolve_file_path(file_path: str) -> Path:
    raw = Path(file_path)
    candidates = [
        raw,
        Path.cwd() / file_path.lstrip("/\\"),
        Path.cwd() / "uploads" / file_path.lstrip("/\\").replace("uploads/", "").replace("uploads\\", ""),
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()

    raise FileNotFoundError(f"Archivo no encontrado para OCR: {file_path}")


def _preprocess_image(image_path: Path) -> Image.Image:
    image = Image.open(image_path).convert("L")
    image = ImageOps.exif_transpose(image)
    image = ImageOps.autocontrast(image)
    image = image.filter(ImageFilter.SHARPEN)
    image = image.point(lambda x: 0 if x < 155 else 255, mode="1")
    return image.convert("L")


def _extract_text_and_confidence(image: Image.Image) -> tuple[str, float | None]:
    extracted_text = pytesseract.image_to_string(image, config=TESSERACT_CONFIG).strip()
    data = pytesseract.image_to_data(image, config=TESSERACT_CONFIG, output_type=Output.DICT)

    confidences = []
    for value in data.get("conf", []):
        try:
            score = float(value)
            if score >= 0:
                confidences.append(score)
        except (TypeError, ValueError):
            continue

    avg_conf = round(sum(confidences) / len(confidences), 2) if confidences else None
    return extracted_text, avg_conf


def extract_text_from_evidence_record(db: Session, evidence: Evidence) -> dict:
    if not evidence.file_type.lower().startswith("image/"):
        raise ValueError("Solo se permite OCR sobre evidencias de imagen")

    image_path = _resolve_file_path(evidence.file_path)
    processed_image = _preprocess_image(image_path)
    extracted_text, confidence = _extract_text_and_confidence(processed_image)

    evidence.ocr_extracted_text = extracted_text
    evidence.ocr_confidence = confidence
    evidence.ocr_processed = True
    evidence.ocr_last_processed_at = datetime.utcnow()
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
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not evidence:
        return None

    return extract_text_from_evidence_record(db, evidence)
