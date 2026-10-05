import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

logger = logging.getLogger(__name__)

METRICS_DIR = Path("metrics/carbon")
METRICS_DIR.mkdir(parents=True, exist_ok=True)


@contextmanager
def track_ai_emissions(
    task_name: str,
    inspection_id: int | None = None,
) -> Generator[object | None, None, None]:
    """
    Context manager para medir emisiones de CO2eq y consumo energético
    en tareas de inferencia de IA (OCR, Whisper, LLM).

    Garantiza resiliencia total: si CodeCarbon o el hardware fallan al iniciar
    o registrar métricas, se captura la excepción y se continúa con el flujo
    del negocio. Las excepciones de la lógica del llamador no son suprimidas.
    """
    tracker = None
    try:
        from codecarbon import OfflineEmissionsTracker

        tracker = OfflineEmissionsTracker(
            country_iso_code="PER",
            project_name="smart-inspection",
            measure_power_secs=1,
            output_dir=str(METRICS_DIR),
            output_file=f"emissions_{task_name}.csv",
            log_level="warning",
        )
        tracker.start()
    except Exception as exc:
        logger.warning(
            "No se pudo iniciar el seguimiento de emisiones para '%s' (inspección %s): %s",
            task_name,
            inspection_id,
            exc,
        )
        tracker = None

    try:
        yield tracker
    finally:
        if tracker is not None:
            try:
                tracker.stop()
            except Exception as exc:
                logger.warning(
                    "Error al detener el tracker de emisiones para '%s' (inspección %s): %s",
                    task_name,
                    inspection_id,
                    exc,
                )