"""
Adaptador de PaddleOCR con parámetros optimizados para rendimiento.

Responsabilidades:
- Singleton del motor PaddleOCR con ``det_limit_side_len=960``.
- Clasificador de ángulo desactivado para ahorrar inferencia.
- Recolección de basura forzada tras cada predicción.
"""

from __future__ import annotations

import gc
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

try:
    from paddleocr import PaddleOCR
except ImportError:
    PaddleOCR = None  # type: ignore[assignment,misc]

_paddle_instance: PaddleOCR | None = None


# ── Inicialización ────────────────────────────────────────────

def get_paddle_engine() -> PaddleOCR:
    """Devuelve (o crea) la instancia singleton de PaddleOCR.

    Configuración de rendimiento aplicada:
    - ``det_limit_side_len=960`` / ``det_limit_type='max'``:
      limita el tensor de detección DBNet para evitar picos de RAM.
    - ``use_angle_cls=False`` (equiv. ``use_doc_orientation_classify``):
      omite el clasificador de rotación si no se requiere.
    - ``cpu_threads=1`` + variables ``OMP/MKL`` ya fijadas en ``ocr_service``:
      previene *thread explosion* en CPU.
    """
    global _paddle_instance

    if PaddleOCR is None:
        raise RuntimeError(
            "paddleocr no está instalado correctamente en el entorno"
        )

    if _paddle_instance is None:
        logger.info("Inicializando PaddleOCR con det_limit_side_len=960")
        _paddle_instance = PaddleOCR(
            lang="es",
            device="cpu",
            enable_mkldnn=False,
            cpu_threads=1,
            det_limit_side_len=960,
            det_limit_type="max",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )

    return _paddle_instance


# ── Extracción ────────────────────────────────────────────────

def collect_texts_and_scores(
    node: Any,
    texts: list[str],
    scores: list[float],
) -> None:
    """Recorre recursivamente la estructura de resultado de PaddleOCR
    y acumula textos reconocidos y sus scores de confianza."""
    if node is None:
        return

    if isinstance(node, dict):
        if "rec_texts" in node and isinstance(
            node.get("rec_texts"), (list, tuple)
        ):
            for text in node.get("rec_texts") or []:
                normalized_text = str(text).strip()
                if normalized_text:
                    texts.append(normalized_text)

        if "rec_scores" in node and isinstance(
            node.get("rec_scores"), (list, tuple)
        ):
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


def extract_with_paddle(image_path: Path) -> tuple[str, float | None]:
    """Ejecuta PaddleOCR sobre la imagen y retorna (texto, confianza).

    Fuerza ``gc.collect()`` tras la inferencia para liberar buffers
    internos de OpenCV/NumPy que PaddleOCR no libera por sí solo.
    """
    ocr = get_paddle_engine()

    try:
        results = list(ocr.predict(str(image_path)))
    finally:
        # Liberar buffers residuales de OpenCV/NumPy
        gc.collect()

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

    extracted_text = " ".join(dict.fromkeys(t for t in texts if t.strip()))
    confidence = round(sum(scores) / len(scores), 2) if scores else None

    return extracted_text, confidence
