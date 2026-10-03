"""
Pipeline de normalización de imagen previo al OCR.

Responsabilidades:
- Corrección de rotación EXIF.
- Conversión de modos de color no estándar (RGBA, CMYK, P, LA) a RGB.
- Downscaling proporcional defensivo (lado mayor <= MAX_SIDE_PX).
- Validación de integridad antes de entregar al motor OCR.
"""

from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path
from typing import Final

from PIL import Image, ImageFilter, ImageOps, UnidentifiedImageError

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pass  # pillow-heif opcional; sin él, archivos HEIC fallarán con UnidentifiedImageError

logger = logging.getLogger(__name__)

# ── Constantes ────────────────────────────────────────────────
MAX_SIDE_PX: Final[int] = 1920
"""Lado mayor máximo permitido antes de pasar al motor OCR."""

RESAMPLING_FILTER: Final[Image.Resampling] = Image.Resampling.LANCZOS
"""Filtro de remuestreo que preserva nitidez en textos y placas."""


# ── Funciones públicas ────────────────────────────────────────

def validate_image_integrity(image_path: Path) -> None:
    """Abre y verifica los datos completos de la imagen.

    Lanza ``UnidentifiedImageError`` o ``OSError`` si el archivo
    está corrupto, truncado o no es una imagen válida.
    """
    with Image.open(image_path) as img:
        img.verify()


def normalize_image(
    image_path: Path,
    *,
    max_side: int = MAX_SIDE_PX,
    apply_sharpen: bool = True,
    convert_grayscale: bool = True,
) -> Image.Image:
    """Devuelve una imagen normalizada lista para OCR **sin guardar a disco**.

    Pasos:
    1. Corrección de orientación EXIF.
    2. Conversión a RGB (desde RGBA, CMYK, P, LA, etc.).
    3. *Downscaling* proporcional si el lado mayor excede ``max_side``.
    4. (Opcional) Conversión a escala de grises + autocontraste + *sharpen*.

    Parameters
    ----------
    image_path:
        Ruta absoluta o relativa a la imagen fuente.
    max_side:
        Dimensión máxima permitida para el lado mayor.
    apply_sharpen:
        Si ``True``, aplica filtro ``SHARPEN`` tras autocontraste.
    convert_grayscale:
        Si ``True``, convierte a escala de grises para Tesseract/PaddleOCR.
    """
    image = Image.open(image_path)

    # 1. Rotación EXIF
    image = ImageOps.exif_transpose(image)

    # 2. Conversión a RGB
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")

    # 3. Downscaling defensivo
    width, height = image.size
    longest_side = max(width, height)
    if longest_side > max_side:
        scale = max_side / longest_side
        new_width = int(width * scale)
        new_height = int(height * scale)
        logger.info(
            "Downscaling imagen OCR: %dx%d -> %dx%d (factor %.2f)",
            width, height, new_width, new_height, scale,
        )
        image = image.resize((new_width, new_height), RESAMPLING_FILTER)

    # 4. Mejora de contraste y nitidez
    if convert_grayscale:
        image = ImageOps.grayscale(image)

    image = ImageOps.autocontrast(image)

    if apply_sharpen:
        image = image.filter(ImageFilter.SHARPEN)

    return image


def normalize_and_save(
    image_path: Path,
    *,
    max_side: int = MAX_SIDE_PX,
    suffix: str = "_preprocessed.png",
) -> Path:
    """Normaliza la imagen y la guarda en disco junto al archivo original.

    Retorna la ruta del archivo preprocesado.
    """
    image = normalize_image(
        image_path,
        max_side=max_side,
        apply_sharpen=True,
        convert_grayscale=True,
    )

    processed_path = image_path.with_name(f"{image_path.stem}{suffix}")
    image.save(processed_path, optimize=True)

    return processed_path


def normalize_to_buffer(
    image_path: Path,
    *,
    max_side: int = MAX_SIDE_PX,
    output_format: str = "PNG",
) -> BytesIO:
    """Normaliza la imagen y la devuelve como buffer en memoria.

    Útil para motores que aceptan file-like objects sin necesidad
    de escritura intermedia en disco.
    """
    image = normalize_image(
        image_path,
        max_side=max_side,
        apply_sharpen=True,
        convert_grayscale=True,
    )
    buffer = BytesIO()
    image.save(buffer, format=output_format, optimize=True)
    buffer.seek(0)
    return buffer
