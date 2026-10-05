from unittest.mock import MagicMock, patch
import pytest

from app.core.carbon import METRICS_DIR, track_ai_emissions


def test_metrics_directory_exists():
    """Verifica que el directorio de métricas esté definido y exista."""
    assert METRICS_DIR.name == "carbon"
    assert METRICS_DIR.parent.name == "metrics"
    assert METRICS_DIR.exists()


def test_track_ai_emissions_nominal():
    """Verifica la ejecución nominal del context manager con CodeCarbon."""
    executed = False
    with track_ai_emissions(task_name="test_nominal", inspection_id=101) as tracker:
        executed = True
        assert tracker is not None

    assert executed is True


def test_track_ai_emissions_resilient_on_tracker_init_failure():
    """
    Verifica que si la inicialización de CodeCarbon arroja una excepción,
    el flujo del negocio continúa sin interrupciones y el bloque interno se ejecuta.
    """
    executed = False
    with patch(
        "codecarbon.OfflineEmissionsTracker",
        side_effect=RuntimeError("Fallo de acceso a hardware RAPL"),
    ):
        with track_ai_emissions(task_name="test_failure", inspection_id=102) as tracker:
            executed = True
            assert tracker is None

    assert executed is True


def test_track_ai_emissions_resilient_on_tracker_start_failure():
    """
    Verifica que si tracker.start() falla, la excepción sea capturada
    y el flujo de negocio no se interrumpa.
    """
    mock_tracker = MagicMock()
    mock_tracker.start.side_effect = PermissionError("Sin permisos de telemetría")

    executed = False
    with patch("codecarbon.OfflineEmissionsTracker", return_value=mock_tracker):
        with track_ai_emissions(task_name="test_start_failure", inspection_id=103) as tracker:
            executed = True
            assert tracker is None

    assert executed is True


def test_track_ai_emissions_resilient_on_tracker_stop_failure():
    """
    Verifica que si tracker.stop() falla al persistir métricas,
    la excepción sea capturada sin afectar el resultado del llamador.
    """
    mock_tracker = MagicMock()
    mock_tracker.stop.side_effect = OSError("Disco lleno al escribir CSV")

    executed = False
    with patch("codecarbon.OfflineEmissionsTracker", return_value=mock_tracker):
        with track_ai_emissions(task_name="test_stop_failure", inspection_id=104) as tracker:
            executed = True
            assert tracker is not None

    assert executed is True
    mock_tracker.stop.assert_called_once()


def test_track_ai_emissions_does_not_suppress_business_exceptions():
    """
    Verifica que las excepciones que ocurran en la lógica del negocio
    dentro del bloque 'with' NO sean suprimidas y se propaguen adecuadamente.
    """
    with pytest.raises(ValueError, match="Error en inferencia de negocio"):
        with track_ai_emissions(task_name="test_business_error", inspection_id=105):
            raise ValueError("Error en inferencia de negocio")
