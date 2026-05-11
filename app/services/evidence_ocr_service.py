from datetime import datetime, timezone
from pathlib import Path

import pytesseract
from PIL import Image, ImageOps
from pytesseract import Output
from sqlalchemy.orm import Session

from app.db.models import Evidence


def _load_image(image_path: Path) -> Image.Image:
    image = Image.open(image_path)
    image = ImageOps.exif_transpose(image)
    image = image.convert("L")
    image = ImageOps.autocontrast(image)
    return image

def _extract_text_and_confidence(image: Image.Image) -> tuple[str | None, float | None]:
    data = pytesseract.image_to_data(image, output_type=Output.DICT, config="--oem 3 --psm 6")

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
    avg_confidence = round(sum(confidences) / len(confidences), 2) if confidences else None

    return extracted_text, avg_confidence

def process_evidence_ocr(db: Session, evidence_id: int) -> Evidence | None:
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not evidence:
        return None

    if not evidence.file_type.startswith("image/"):
        raise ValueError("El OCR solo está habilitado para imágenes")

    absolute_path = Path.cwd() / evidence.file_path
    if not absolute_path.exists():
        raise ValueError("No se encontró el archivo de la evidencia")

    image = _load_image(absolute_path)
    extracted_text, confidence = _extract_text_and_confidence(image)

    evidence.ocr_extracted_text = extracted_text
    evidence.ocr_confidence = confidence
    evidence.ocr_processed = True
    evidence.ocr_last_processed_at = datetime.now(timezone.utc)

    db.add(evidence)
    db.commit()
    db.refresh(evidence)
    return evidence