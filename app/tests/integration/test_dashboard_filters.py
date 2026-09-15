from datetime import datetime, timedelta, timezone

import pytest

from conftest import log_api_response


api_prefix = "/api/v1"


def create_inspection(
    client,
    code,
    inspection_date,
):
    response = client.post(
        f"{api_prefix}/inspections",
        json={
            "code": code,
            "client_name": "Empresa Dashboard S.A.C.",
            "equipment_type": "Camión",
            "inspection_type": "Inspección técnica",
            "inspection_date": inspection_date,
            "location": "Trujillo",
            "requested_by": "Prueba de dashboard",
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


def create_completed_productivity(
    client,
    inspection_id,
    inspector_name,
    scheduled_date,
    duration_minutes,
):
    finished_at = datetime.now(timezone.utc)
    started_at = finished_at - timedelta(minutes=duration_minutes)

    create_response = client.post(
        f"{api_prefix}/productivity",
        json={
            "inspection_id": inspection_id,
            "inspector_name": inspector_name,
            "scheduled_date": scheduled_date,
            "operational_status": "scheduled",
        },
    )

    log_api_response(
        "POST",
        f"{api_prefix}/productivity",
        create_response,
    )

    assert create_response.status_code == 201, (
        f"Error al crear productividad: "
        f"status_code={create_response.status_code}, "
        f"response={create_response.text}"
    )

    start_response = client.patch(
        f"{api_prefix}/productivity/inspection/{inspection_id}/start",
        json={
            "report_started_at": started_at.isoformat(),
        },
    )

    log_api_response(
        "PATCH",
        f"{api_prefix}/productivity/inspection/{inspection_id}/start",
        start_response,
    )

    assert start_response.status_code == 200, (
        f"Error al iniciar productividad: "
        f"status_code={start_response.status_code}, "
        f"response={start_response.text}"
    )

    finish_response = client.patch(
        f"{api_prefix}/productivity/inspection/{inspection_id}/finish",
        json={
            "report_finished_at": finished_at.isoformat(),
            "operational_status": "completed",
        },
    )

    log_api_response(
        "PATCH",
        f"{api_prefix}/productivity/inspection/{inspection_id}/finish",
        finish_response,
    )

    assert finish_response.status_code == 200, (
        f"Error al finalizar productividad: "
        f"status_code={finish_response.status_code}, "
        f"response={finish_response.text}"
    )

    return finish_response.json()


def find_inspector_item(by_inspector, inspector_name):
    return next(
        item
        for item in by_inspector
        if item["inspector_name"] == inspector_name
    )


def test_dashboard_filters_by_date_range_and_inspector(client):
    ana_july_one = create_inspection(
        client=client,
        code="INT-DASH-001",
        inspection_date="2026-07-01",
    )
    ana_july_two = create_inspection(
        client=client,
        code="INT-DASH-002",
        inspection_date="2026-07-10",
    )
    luis_july = create_inspection(
        client=client,
        code="INT-DASH-003",
        inspection_date="2026-07-15",
    )
    ana_august = create_inspection(
        client=client,
        code="INT-DASH-004",
        inspection_date="2026-08-05",
    )
    luis_june = create_inspection(
        client=client,
        code="INT-DASH-005",
        inspection_date="2026-06-20",
    )

    ana_july_one_productivity = create_completed_productivity(
        client=client,
        inspection_id=ana_july_one["id"],
        inspector_name="Ana Pérez",
        scheduled_date="2026-07-01",
        duration_minutes=10,
    )
    ana_july_two_productivity = create_completed_productivity(
        client=client,
        inspection_id=ana_july_two["id"],
        inspector_name="Ana Pérez",
        scheduled_date="2026-07-10",
        duration_minutes=30,
    )
    luis_july_productivity = create_completed_productivity(
        client=client,
        inspection_id=luis_july["id"],
        inspector_name="Luis Torres",
        scheduled_date="2026-07-15",
        duration_minutes=15,
    )
    ana_august_productivity = create_completed_productivity(
        client=client,
        inspection_id=ana_august["id"],
        inspector_name="Ana Pérez",
        scheduled_date="2026-08-05",
        duration_minutes=18,
    )
    luis_june_productivity = create_completed_productivity(
        client=client,
        inspection_id=luis_june["id"],
        inspector_name="Luis Torres",
        scheduled_date="2026-06-20",
        duration_minutes=25,
    )

    assert ana_july_one_productivity["duration_minutes"] == 10
    assert ana_july_one_productivity["met_goal"] is True

    assert ana_july_two_productivity["duration_minutes"] == 30
    assert ana_july_two_productivity["met_goal"] is False

    assert luis_july_productivity["duration_minutes"] == 15
    assert luis_july_productivity["met_goal"] is True

    assert ana_august_productivity["duration_minutes"] == 18
    assert ana_august_productivity["met_goal"] is True

    assert luis_june_productivity["duration_minutes"] == 25
    assert luis_june_productivity["met_goal"] is False

    july_dashboard_response = client.get(
        f"{api_prefix}/productivity/dashboard",
        params={
            "date_from": "2026-07-01",
            "date_to": "2026-07-31",
        },
    )

    log_api_response(
        "GET",
        f"{api_prefix}/productivity/dashboard"
        "?date_from=2026-07-01&date_to=2026-07-31",
        july_dashboard_response,
    )

    assert july_dashboard_response.status_code == 200, (
        f"Error al consultar dashboard de julio: "
        f"status_code={july_dashboard_response.status_code}, "
        f"response={july_dashboard_response.text}"
    )

    july_dashboard = july_dashboard_response.json()
    july_summary = july_dashboard["summary"]
    july_by_inspector = july_dashboard["by_inspector"]

    assert july_summary["total_inspections"] == 3
    assert july_summary["completed_reports"] == 3
    assert july_summary["average_report_minutes"] == pytest.approx(
        18.33,
        abs=0.01,
    )
    assert july_summary["on_time_count"] == 2
    assert july_summary["on_time_percentage"] == pytest.approx(
        66.67,
        abs=0.01,
    )
    assert july_summary["goal_minutes"] == 20

    assert len(july_by_inspector) == 2

    ana_july = find_inspector_item(
        july_by_inspector,
        "Ana Pérez",
    )
    luis_july_item = find_inspector_item(
        july_by_inspector,
        "Luis Torres",
    )

    assert ana_july["assigned_inspections"] == 2
    assert ana_july["completed_reports"] == 2
    assert ana_july["average_report_minutes"] == 20.0
    assert ana_july["on_time_count"] == 1
    assert ana_july["on_time_percentage"] == 50.0

    assert luis_july_item["assigned_inspections"] == 1
    assert luis_july_item["completed_reports"] == 1
    assert luis_july_item["average_report_minutes"] == 15.0
    assert luis_july_item["on_time_count"] == 1
    assert luis_july_item["on_time_percentage"] == 100.0

    ana_july_dashboard_response = client.get(
        f"{api_prefix}/productivity/dashboard",
        params={
            "date_from": "2026-07-01",
            "date_to": "2026-07-31",
            "inspector_name": "Ana Pérez",
        },
    )

    log_api_response(
        "GET",
        f"{api_prefix}/productivity/dashboard"
        "?date_from=2026-07-01"
        "&date_to=2026-07-31"
        "&inspector_name=Ana%20Pérez",
        ana_july_dashboard_response,
    )

    assert ana_july_dashboard_response.status_code == 200, (
        f"Error al filtrar dashboard por inspector: "
        f"status_code={ana_july_dashboard_response.status_code}, "
        f"response={ana_july_dashboard_response.text}"
    )

    ana_july_dashboard = ana_july_dashboard_response.json()
    ana_july_summary = ana_july_dashboard["summary"]
    ana_july_by_inspector = ana_july_dashboard["by_inspector"]

    assert ana_july_summary["total_inspections"] == 2
    assert ana_july_summary["completed_reports"] == 2
    assert ana_july_summary["average_report_minutes"] == 20.0
    assert ana_july_summary["on_time_count"] == 1
    assert ana_july_summary["on_time_percentage"] == 50.0
    assert ana_july_summary["goal_minutes"] == 20

    assert len(ana_july_by_inspector) == 1

    ana_filtered = ana_july_by_inspector[0]

    assert ana_filtered["inspector_name"] == "Ana Pérez"
    assert ana_filtered["assigned_inspections"] == 2
    assert ana_filtered["completed_reports"] == 2
    assert ana_filtered["average_report_minutes"] == 20.0
    assert ana_filtered["on_time_count"] == 1
    assert ana_filtered["on_time_percentage"] == 50.0

    august_dashboard_response = client.get(
        f"{api_prefix}/productivity/dashboard",
        params={
            "date_from": "2026-08-01",
            "date_to": "2026-08-31",
            "inspector_name": "Ana Pérez",
        },
    )

    log_api_response(
        "GET",
        f"{api_prefix}/productivity/dashboard"
        "?date_from=2026-08-01"
        "&date_to=2026-08-31"
        "&inspector_name=Ana%20Pérez",
        august_dashboard_response,
    )

    assert august_dashboard_response.status_code == 200, (
        f"Error al consultar dashboard de agosto: "
        f"status_code={august_dashboard_response.status_code}, "
        f"response={august_dashboard_response.text}"
    )

    august_dashboard = august_dashboard_response.json()
    august_summary = august_dashboard["summary"]
    august_by_inspector = august_dashboard["by_inspector"]

    assert august_summary["total_inspections"] == 1
    assert august_summary["completed_reports"] == 1
    assert august_summary["average_report_minutes"] == 18.0
    assert august_summary["on_time_count"] == 1
    assert august_summary["on_time_percentage"] == 100.0

    assert len(august_by_inspector) == 1
    assert august_by_inspector[0]["inspector_name"] == "Ana Pérez"
    assert august_by_inspector[0]["assigned_inspections"] == 1
    assert august_by_inspector[0]["completed_reports"] == 1
    assert august_by_inspector[0]["average_report_minutes"] == 18.0
    assert august_by_inspector[0]["on_time_count"] == 1
    assert august_by_inspector[0]["on_time_percentage"] == 100.0