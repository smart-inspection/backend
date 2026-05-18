import os

os.environ["PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT"] = "0"
os.environ["FLAGS_use_mkldnn"] = "0"

from pathlib import Path
from datetime import datetime

from PIL import Image, ImageOps, ImageFilter
from sqlalchemy.orm import Session

from app.db.models import Evidence

try:
    from paddleocr import PaddleOCR
except ImportError:
    PaddleOCR = None

_PADDLE_OCR = None

def _get_ocr_engine() -> PaddleOCR:
    global _PADDLE_OCR

    if PaddleOCR is None:
        raise RuntimeError(
            "PaddleOCR no está instalado correctamente en el entorno virtual."
        )

    if _PADDLE_OCR is None:
        _PADDLE_OCR = PaddleOCR(
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            engine="paddle",
        )

    return _PADDLE_OCR

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

def _preprocess_image(image_path: Path) -> Path:
    image = Image.open(image_path)
    image = ImageOps.exif_transpose(image)
    image = image.convert("RGB")

    gray = ImageOps.grayscale(image)
    gray = ImageOps.autocontrast(gray)
    gray = gray.filter(ImageFilter.SHARPEN)

    enlarged = gray.resize((gray.width * 3, gray.height * 3))
    processed_path = image_path.with_name(f"{image_path.stem}_paddle_preprocessed.png")
    enlarged.save(processed_path)

    return processed_path

def _extract_text_and_confidence(image_path: Path) -> tuple[str, float | None]:
    ocr = _get_ocr_engine()
    results = list(ocr.predict(str(image_path)))

    for i, res in enumerate(results):
        try:
            print(f"[PADDLE DEBUG] result #{i} type={type(res)}")
            if hasattr(res, "print"):
                res.print()
            if hasattr(res, "save_to_json"):
                res.save_to_json("output")
        except Exception as e:
            print(f"[PADDLE DEBUG] error printing result: {e}")

    lines: list[str] = []
    confidences: list[float] = []

    for res in results:
        data = None

        if hasattr(res, "json"):
            try:
                print("[PADDLE DEBUG] json =", res.json)
            except Exception:
                pass

        if isinstance(res, dict):
            data = res.get("res", res)
        elif hasattr(res, "res"):
            data = getattr(res, "res")
        else:
            data = None

        if isinstance(data, dict):
            if "rec_texts" in data:
                for text in data.get("rec_texts", []) or []:
                    text = str(text).strip()
                    if text:
                        lines.append(text)

                for score in data.get("rec_scores", []) or []:
                    try:
                        confidences.append(float(score) * 100)
                    except Exception:
                        pass

            elif "rec_text" in data:
                text = str(data.get("rec_text", "")).strip()
                score = data.get("rec_score")
                if text:
                    lines.append(text)
                if score is not None:
                    try:
                        confidences.append(float(score) * 100)
                    except Exception:
                        pass

    extracted_text = "\n".join(lines).strip()
    avg_conf = round(sum(confidences) / len(confidences), 2) if confidences else None
    return extracted_text, avg_conf

def _collect_texts_and_scores(node, texts, scores):
    if node is None:
        return

    if isinstance(node, dict):
        if "rec_texts" in node and isinstance(node.get("rec_texts"), (list, tuple)):
            for text in node.get("rec_texts") or []:
                text = str(text).strip()
                if text:
                    texts.append(text)

        if "rec_scores" in node and isinstance(node.get("rec_scores"), (list, tuple)):
            for score in node.get("rec_scores") or []:
                try:
                    scores.append(float(score) * 100)
                except Exception:
                    pass

        if "rec_text" in node:
            text = str(node.get("rec_text", "")).strip()
            if text:
                texts.append(text)

        if "rec_score" in node:
            try:
                scores.append(float(node.get("rec_score")) * 100)
            except Exception:
                pass

        for value in node.values():
            _collect_texts_and_scores(value, texts, scores)

    elif isinstance(node, (list, tuple)):
        for item in node:
            _collect_texts_and_scores(item, texts, scores)


def _extract_text_and_confidence(image_path: Path) -> tuple[str, float | None]:
    ocr = _get_ocr_engine()
    results = list(ocr.predict(str(image_path)))

    texts: list[str] = []
    scores: list[float] = []

    for res in results:
        if isinstance(res, dict):
            payload = res
        elif hasattr(res, "res"):
            payload = res.res
        else:
            payload = None

        _collect_texts_and_scores(payload, texts, scores)

    extracted_text = "\n".join(dict.fromkeys(t for t in texts if t)).strip()
    confidence = round(sum(scores) / len(scores), 2) if scores else None
    return extracted_text, confidence

def extract_text_from_evidence_record(db: Session, evidence: Evidence) -> dict:
    if not evidence.file_type.lower().startswith("image/"):
        raise ValueError("Solo se permite OCR sobre evidencias de imagen")

    image_path = _resolve_file_path(evidence.file_path)
    processed_path = _preprocess_image(image_path)
    extracted_text, confidence = _extract_text_and_confidence(processed_path)

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