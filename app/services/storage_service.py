import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

UPLOADS_ROOT = Path("uploads")

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
ALLOWED_AUDIO_EXTENSIONS = {".webm", ".wav", ".mp3", ".m4a", ".ogg"}

ALLOWED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png"}
ALLOWED_AUDIO_MIME_TYPES = {
    "audio/webm",
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp4",
    "audio/x-m4a",
    "audio/ogg",
    "video/webm",
}


def _normalize_content_type(file: UploadFile) -> str:
    raw_content_type = (file.content_type or "").lower().strip()
    return raw_content_type.split(";", 1)[0].strip()


def _validate_file_type(suffix: str, content_type: str) -> None:
    allowed_extensions = ALLOWED_IMAGE_EXTENSIONS | ALLOWED_AUDIO_EXTENSIONS
    allowed_mime_types = ALLOWED_IMAGE_MIME_TYPES | ALLOWED_AUDIO_MIME_TYPES

    if suffix not in allowed_extensions:
        raise ValueError(
            "Solo se permiten archivos .jpg, .jpeg, .png, .webm, .wav, .mp3, .m4a, .ogg"
        )

    if content_type and content_type not in allowed_mime_types:
        raise ValueError(f"Tipo de archivo no permitido: {content_type}")


def save_evidence_upload(inspection_id: int, file: UploadFile) -> tuple[str, str]:
    suffix = Path(file.filename or "").suffix.lower()
    content_type = _normalize_content_type(file)

    if not suffix:
        raise ValueError("El archivo debe incluir una extensión válida.")

    _validate_file_type(suffix, content_type)

    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)

    if size > MAX_FILE_SIZE_BYTES:
        raise ValueError("Peso de archivo excedido")

    target_dir = UPLOADS_ROOT / "inspections" / str(inspection_id)
    target_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid4().hex}{suffix}"
    relative_path = Path("uploads") / "inspections" / str(inspection_id) / filename
    absolute_path = Path.cwd() / relative_path

    with absolute_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return str(relative_path).replace("\\", "/"), content_type