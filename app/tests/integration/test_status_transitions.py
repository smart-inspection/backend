from datetime import datetime, timedelta, timezone

import pytest

from conftest import log_api_response


api_prefix = "/api/v1"


def create_inspection(client):
    response = client.post(
        f"{api_prefix}/inspections",
        json={
            "code": "INT-STATUS-001",
            "client_name": "Empresa Estados S.A.C.",
            "equipment_type": "Camión",
            "inspection_type": "Inspección técnica",
            "inspection_date": "2026-07-10",
            "location": "Trujillo",
            "requested_by": "Prueba de transiciones",
            "status": "draft",
        },
    )

    log_api_response(
        "POST",
        f"{api_prefix}/inspections",
        response,
    )

    assert response.status_code == 201, (
        f"Error al crear inspección: "
        f"status_code={response.status_code}, "
        f"response={response.text}"
    )

    return response.json()


def create_report_draft(client, inspection_id):
    response = client.post(
        f"{api_prefix}/report-drafts/generate/{inspection_id}",
        json={
            "template_version": "status-transitions-v1",
        },
    )

    log_api_response(
        "POST",
        f"{api_prefix}/report-drafts/generate/{inspection_id}",
        response,
    )

    assert response.status_code == 201, (
        f"Error al generar borrador: "
        f"status_code={response.status_code}, "
        f"response={response.text}"
    )

    return response.json()


def get_productivity(client, inspection_id):
    response = client.get(
        f"{api_prefix}/productivity/inspection/{inspection_id}",
    )

    log_api_response(
        "GET",
        f"{api_prefix}/productivity/inspection/{inspection_id}",
        response,
    )

    assert response.status_code == 200, (
        f"Error al consultar productividad: "
        f"status_code={response.status_code}, "
        f"response={response.text}"
    )

    return response.json()


def update_report_status(
    client,
    report_draft_id,
    status,
    notes,
):
    response = client.patch(
        f"{api_prefix}/reports/{report_draft_id}/status",
        json={
            "status": status,
            "notes": notes,
        },
    )

    log_api_response(
        "PATCH",
        f"{api_prefix}/reports/{report_draft_id}/status",
        response,
    )

    assert response.status_code == 200, (
        f"Error al actualizar estado a {status}: "
        f"status_code={response.status_code}, "
        f"response={response.text}"
    )

    return response.json()


def test_report_status_transitions_sync_operational_productivity(client):
    inspection = create_inspection(client)
    inspection_id = inspection["id"]

    assert inspection["status"] == "draft"

    initial_productivity = get_productivity(
        client=client,
        inspection_id=inspection_id,
    )

    assert initial_productivity["inspection_id"] == inspection_id
    assert initial_productivity["operational_status"] == "pending"
    assert initial_productivity["report_started_at"] is None
    assert initial_productivity["report_finished_at"] is None
    assert initial_productivity["duration_minutes"] is None
    assert initial_productivity["met_goal"] is None

    report_draft = create_report_draft(
        client=client,
        inspection_id=inspection_id,
    )
    report_draft_id = report_draft["id"]

    assert report_draft["inspection_id"] == inspection_id
    assert report_draft["status"] == "draft"

    in_review_report = update_report_status(
        client=client,
        report_draft_id=report_draft_id,
        status="in_review",
        notes="El informe ingresó a revisión.",
    )

    assert in_review_report["status"] == "in_review"

    in_progress_productivity = get_productivity(
        client=client,
        inspection_id=inspection_id,
    )

    assert in_progress_productivity["inspection_id"] == inspection_id
    assert in_progress_productivity["operational_status"] == "in_progress"
    assert in_progress_productivity["report_started_at"] is not None
    assert in_progress_productivity["report_finished_at"] is None
    assert in_progress_productivity["duration_minutes"] is None
    assert in_progress_productivity["met_goal"] is None

    controlled_started_at = (
        datetime.now(timezone.utc) - timedelta(minutes=15)
    )

    start_response = client.patch(
        f"{api_prefix}/productivity/inspection/{inspection_id}/start",
        json={
            "report_started_at": controlled_started_at.isoformat(),
        },
    )

    log_api_response(
        "PATCH",
        f"{api_prefix}/productivity/inspection/{inspection_id}/start",
        start_response,
    )

    assert start_response.status_code == 200, (
        f"Error al establecer inicio controlado: "
        f"status_code={start_response.status_code}, "
        f"response={start_response.text}"
    )

    started_productivity = start_response.json()

    assert started_productivity["operational_status"] == "in_progress"
    assert started_productivity["report_started_at"] is not None

    finalized_report = update_report_status(
        client=client,
        report_draft_id=report_draft_id,
        status="finalized",
        notes="El informe fue finalizado.",
    )

    assert finalized_report["status"] == "finalized"

    completed_productivity = get_productivity(
        client=client,
        inspection_id=inspection_id,
    )

    assert completed_productivity["inspection_id"] == inspection_id
    assert completed_productivity["operational_status"] == "completed"
    assert completed_productivity["report_started_at"] is not None
    assert completed_productivity["report_finished_at"] is not None
    assert completed_productivity["duration_minutes"] is not None
    assert completed_productivity["duration_minutes"] == pytest.approx(
        15,
        abs=0.1,
    )
    assert completed_productivity["duration_minutes"] <= 20
    assert completed_productivity["met_goal"] is True