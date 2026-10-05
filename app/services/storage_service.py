import logging
import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from PIL import Image, ImageOps

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pass

logger = logging.getLogger(__name__)

_HEIC_EXTENSIONS: set[str] = {".heic", ".heif"}

UPLOADS_ROOT = Path("uploads")

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".heif"}
ALLOWED_AUDIO_EXTENSIONS = {".webm", ".wav", ".mp3", ".m4a", ".ogg"}

ALLOWED_IMAGE_MIME_TYPES = {
    "image/jpeg", "image/png",
    "image/heic", "image/heif",
    "image/heic-sequence", "image/heif-sequence",
}

_GENERIC_MIME_TYPES: set[str] = {"application/octet-stream", ""}
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
    """Valida extensión y MIME type del archivo.

    Si el cliente envía un MIME genérico (``application/octet-stream`` o vacío),
    la validación se apoya únicamente en la extensión del archivo.
    Esto ocurre frecuentemente con archivos HEIC desde iOS/Safari.
    """
    allowed_extensions = ALLOWED_IMAGE_EXTENSIONS | ALLOWED_AUDIO_EXTENSIONS
    allowed_mime_types = ALLOWED_IMAGE_MIME_TYPES | ALLOWED_AUDIO_MIME_TYPES

    if suffix not in allowed_extensions:
        raise ValueError(
            "Solo se permiten archivos .jpg, .jpeg, .png, .heic, .heif, .webm, .wav, .mp3, .m4a, .ogg"
        )

    # MIME genérico → confiar en la extensión (ya validada arriba)
    if content_type in _GENERIC_MIME_TYPES:
        return

    if content_type not in allowed_mime_types:
        raise ValueError(f"Tipo de archivo no permitido: {content_type}")


def _convert_heic_to_jpeg(source_path: Path) -> Path:
    """Convierte un archivo HEIC/HEIF a JPEG en la misma ubicación.

    - Corrige orientación EXIF.
    - Convierte a RGB (los HEIC pueden ser RGBA o modos exóticos).
    - Guarda como .jpg con calidad 92 (equilibrio nitidez/peso).
    - Elimina el archivo HEIC original tras la conversión exitosa.

    Retorna la ruta del archivo .jpg resultante.
    """
    image = Image.open(source_path)
    image = ImageOps.exif_transpose(image)

    if image.mode != "RGB":
        image = image.convert("RGB")

    jpeg_path = source_path.with_suffix(".jpg")
    image.save(jpeg_path, format="JPEG", quality=92, optimize=True)
    image.close()

    # Eliminar archivo HEIC original
    try:
        source_path.unlink()
    except OSError:
        pass

    logger.info("HEIC convertido a JPEG: %s -> %s", source_path.name, jpeg_path.name)
    return jpeg_path


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

    # Conversión HEIC/HEIF -> JPEG para compatibilidad web y OCR
    if suffix in _HEIC_EXTENSIONS:
        jpeg_path = _convert_heic_to_jpeg(absolute_path)
        relative_path = Path("uploads") / "inspections" / str(inspection_id) / jpeg_path.name
        content_type = "image/jpeg"

    return str(relative_path).replace("\\", "/"), content_type


def delete_physical_file(file_path: str) -> bool:
    """
    Elimina el archivo físico del disco.
    Acepta rutas relativas o absolutas, con separador '/' o '\\'.
    Retorna True si fue eliminado, False si no existía.
    """
    if not file_path:
        return False

    # Normalizar separadores y limpiar slash inicial
    normalized = file_path.replace("\\", "/").lstrip("/")
    candidate = Path(normalized)

    # Si la ruta es relativa, resolverla desde el directorio de trabajo
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate

    try:
        candidate = candidate.resolve()
        if candidate.exists() and candidate.is_file():
            candidate.unlink()
            return True
        return False
    except OSError:
        return False