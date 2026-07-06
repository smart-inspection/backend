import os

os.environ["PADDLE_PDX_DISABLE_MKLDNN"] = "1"
os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["FLAGS_use_onednn"] = "0"
os.environ["FLAGS_enable_pir_api"] = "0"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

from datetime import datetime
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Evidence

try:
    from paddleocr import PaddleOCR
except ImportError:
    PaddleOCR = None

_paddle_ocr = None


def get_ocr_engine():
    global _paddle_ocr

    if PaddleOCR is None:
        raise RuntimeError("paddleocr no está instalado correctamente en el entorno")

    if _paddle_ocr is None:
        _paddle_ocr = PaddleOCR(
            lang="es",
            device="cpu",
            enable_mkldnn=False,
            cpu_threads=1,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )

    return _paddle_ocr


def resolve_file_path(file_path: str) -> Path:
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


def get_paddle_max_image_width() -> int:
    value = getattr(settings, "paddle_max_image_width", 4000)
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = 4000
    return max(parsed, 1)


def get_paddle_max_image_height() -> int:
    value = getattr(settings, "paddle_max_image_height", 4000)
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = 4000
    return max(parsed, 1)


def preprocess_image(image_path: Path) -> Path:
    image = Image.open(image_path)
    image = ImageOps.exif_transpose(image)
    image = image.convert("RGB")

    max_width = get_paddle_max_image_width()
    max_height = get_paddle_max_image_height()

    image.thumbnail((max_width, max_height))

    gray = ImageOps.grayscale(image)
    gray = ImageOps.autocontrast(gray)
    gray = gray.filter(ImageFilter.SHARPEN)

    processed_path = image_path.with_name(f"{image_path.stem}_paddle_preprocessed.png")
    gray.save(processed_path, optimize=True)

    return processed_path


def collect_texts_and_scores(node, texts, scores):
    if node is None:
        return

    if isinstance(node, dict):
        if "rec_texts" in node and isinstance(node.get("rec_texts"), (list, tuple)):
            for text in node.get("rec_texts") or []:
                normalized_text = str(text).strip()
                if normalized_text:
                    texts.append(normalized_text)

        if "rec_scores" in node and isinstance(node.get("rec_scores"), (list, tuple)):
            for score in node.get("rec_scores") or []:
                try:
                    scores.append(float(score) * 100)
                except (TypeError, ValueError):
                    continue

        if "rec_text" in node:
            normalized_text = str(node.get("rec_text") or "").strip()
            if normalized_text:
                texts.append(normalized_text)

        if "rec_score" in node:
            try:
                scores.append(float(node.get("rec_score")) * 100)
            except (TypeError, ValueError):
                pass

        for value in node.values():
            collect_texts_and_scores(value, texts, scores)

    elif isinstance(node, (list, tuple)):
        for item in node:
            collect_texts_and_scores(item, texts, scores)


def extract_text_and_confidence(image_path: Path) -> tuple[str, float | None]:
    ocr = get_ocr_engine()
    results = list(ocr.predict(str(image_path)))

    texts: list[str] = []
    scores: list[float] = []

    for result in results:
        if isinstance(result, dict):
            payload = result
        elif hasattr(result, "res"):
            payload = result.res
        else:
            payload = None

        collect_texts_and_scores(payload, texts, scores)

    extracted_text = " ".join(dict.fromkeys(text for text in texts if text.strip()))
    confidence = round(sum(scores) / len(scores), 2) if scores else None

    return extracted_text, confidence


def extract_text_from_evidence_record(db: Session, evidence: Evidence) -> dict:
    if not evidence.file_type.lower().startswith("image"):
        raise ValueError("solo se permite OCR sobre evidencias de imagen")

    image_path = resolve_file_path(evidence.file_path)
    processed_path = preprocess_image(image_path)
    extracted_text, confidence = extract_text_and_confidence(processed_path)

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