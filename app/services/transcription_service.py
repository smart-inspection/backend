from pathlib import Path
from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import Inspection, Evidence, Transcription
from app.schemas.transcription import TranscriptionCreate, TranscriptionUpdate


def _resolve_audio_path(file_path: str) -> Path:
    raw = Path(file_path)
    candidates = [
        raw,
        Path.cwd() / file_path.lstrip("/\\"),
        Path.cwd() / "uploads" / file_path.lstrip("/\\").replace("uploads/", "").replace("uploads\\", ""),
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()

    raise FileNotFoundError(f"Archivo de audio no encontrado: {file_path}")


def _mock_confidence(text: str) -> float | None:
    if not text:
        return None
    word_count = len(text.split())
    if word_count >= 20:
        return 92.0
    if word_count >= 10:
        return 88.0
    return 80.0


def _transcribe_with_whisper(audio_path: Path, model_name: str = "base", language: str | None = "es") -> tuple[str, float | None]:
    try:
        import whisper
    except ImportError as exc:
        raise RuntimeError(
            "La librería openai-whisper no está instalada. Ejecuta: pip install openai-whisper"
        ) from exc

    model = whisper.load_model(model_name)
    result = model.transcribe(str(audio_path), language=language, fp16=False)

    text = (result.get("text") or "").strip()
    confidence = _mock_confidence(text)
    return text, confidence


def create_and_process_transcription(db: Session, payload: TranscriptionCreate) -> Transcription:
    inspection = db.query(Inspection).filter(Inspection.id == payload.inspection_id).first()
    if not inspection:
        raise ValueError("Inspection not found")

    if payload.evidence_id is not None:
        evidence = db.query(Evidence).filter(Evidence.id == payload.evidence_id).first()
        if not evidence:
            raise ValueError("Evidence not found")
    else:
        evidence = None

    audio_path = _resolve_audio_path(payload.source_file_path)
    raw_text, confidence = _transcribe_with_whisper(
        audio_path=audio_path,
        model_name=payload.model_name,
        language=payload.language,
    )

    transcription = Transcription(
        inspection_id=payload.inspection_id,
        evidence_id=payload.evidence_id,
        source_file_path=str(audio_path),
        language=payload.language,
        model_name=payload.model_name,
        raw_text=raw_text,
        final_text=raw_text,
        confidence=confidence,
        processed=True,
        edited_manually=False,
    )

    db.add(transcription)
    db.commit()
    db.refresh(transcription)
    return transcription


def list_transcriptions_by_inspection(db: Session, inspection_id: int) -> list[Transcription]:
    return (
        db.query(Transcription)
        .filter(Transcription.inspection_id == inspection_id)
        .order_by(Transcription.id.desc())
        .all()
    )


def get_transcription_by_id(db: Session, transcription_id: int) -> Transcription | None:
    return db.query(Transcription).filter(Transcription.id == transcription_id).first()


def update_transcription_text(
    db: Session,
    transcription_id: int,
    payload: TranscriptionUpdate
) -> Transcription | None:
    transcription = db.query(Transcription).filter(Transcription.id == transcription_id).first()
    if not transcription:
        return None

    transcription.final_text = payload.final_text
    transcription.edited_manually = True
    transcription.updated_at = datetime.utcnow()

    db.add(transcription)
    db.commit()
    db.refresh(transcription)
    return transcription