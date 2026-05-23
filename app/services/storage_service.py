import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

UPLOADS_ROOT = Path("uploads")
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
ALLOWED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png"}

def save_evidence_upload(inspection_id: int, file: UploadFile) -> tuple[str, str]:
    suffix = Path(file.filename or "").suffix.lower()
    content_type = (file.content_type or "").lower()

    print("filename =", file.filename)
    print("content_type =", content_type)

    if suffix not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError("Solo se permiten archivos .jpg, .jpeg, .png")

    if content_type not in ALLOWED_IMAGE_MIME_TYPES:
        raise ValueError(f"Tipo de archivo no permitido: {content_type}")

    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)

    if size > MAX_IMAGE_SIZE_BYTES:
        raise ValueError("Peso de archivo excedido")

    target_dir = UPLOADS_ROOT / "inspections" / str(inspection_id)
    target_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid4().hex}{suffix}"
    relative_path = Path("uploads") / "inspections" / str(inspection_id) / filename
    absolute_path = Path.cwd() / relative_path

    with absolute_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return str(relative_path).replace("\\", "/"), content_type