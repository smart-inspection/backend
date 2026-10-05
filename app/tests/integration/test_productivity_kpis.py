from datetime import datetime, timedelta, timezone

from conftest import log_api_response


api_prefix = "/api/v1"


def create_inspection(client, code, inspection_date):
    response = client.post(
        f"{api_prefix}/inspections",
        json={
            "code": code,
            "client_name": "Empresa KPIs S.A.C.",
            "equipment_type": "Camión",
            "inspection_type": "Inspección técnica",
            "inspection_date": inspection_date,
            "location": "Trujillo",
            "requested_by": "Prueba de integración",
            "status": "draft",
        },
    )
    log_api_response(
        "POST",
        f"{api_prefix}/inspections",
        response,
    )

    assert response.status_code == 201, response.text

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


def test_productivity_kpis_calculate_summary_groups_and_filters(client):
    inspection_one = create_inspection(
        client=client,
        code="INT-KPI-001",
        inspection_date="2026-07-01",
    )
    inspection_two = create_inspection(
        client=client,
        code="INT-KPI-002",
        inspection_date="2026-07-02",
    )
    inspection_three = create_inspection(
        client=client,
        code="INT-KPI-003",
        inspection_date="2026-07-03",
    )
    inspection_four = create_inspection(
        client=client,
        code="INT-KPI-004",
        inspection_date="2026-07-04",
    )

    productivity_one = create_completed_productivity(
        client=client,
        inspection_id=inspection_one["id"],
        inspector_name="Ana Pérez",
        scheduled_date="2026-07-01",
        duration_minutes=10,
    )
    productivity_two = create_completed_productivity(
        client=client,
        inspection_id=inspection_two["id"],
        inspector_name="Ana Pérez",
        scheduled_date="2026-07-02",
        duration_minutes=20,
    )
    productivity_three = create_completed_productivity(
        client=client,
        inspection_id=inspection_three["id"],
        inspector_name="Luis Torres",
        scheduled_date="2026-07-03",
        duration_minutes=30,
    )
    productivity_four = create_completed_productivity(
        client=client,
        inspection_id=inspection_four["id"],
        inspector_name="Luis Torres",
        scheduled_date="2026-07-04",
        duration_minutes=15,
    )

    assert productivity_one["duration_minutes"] == 10
    assert productivity_one["met_goal"] is True

    assert productivity_two["duration_minutes"] == 20
    assert productivity_two["met_goal"] is True

    assert productivity_three["duration_minutes"] == 30
    assert productivity_three["met_goal"] is False

    assert productivity_four["duration_minutes"] == 15
    assert productivity_four["met_goal"] is True

    summary_response = client.get(
        f"{api_prefix}/productivity/summary",
        params={
            "date_from": "2026-07-01",
            "date_to": "2026-07-31",
        },
    )
    log_api_response(
        "GET",
        f"{api_prefix}/productivity/summary",
        summary_response,
    )

    assert summary_response.status_code == 200, summary_response.text

    summary = summary_response.json()

    assert summary["total_inspections"] == 4
    assert summary["completed_reports"] == 4
    assert summary["average_report_minutes"] == 18.75
    assert summary["on_time_count"] == 3
    assert summary["on_time_percentage"] == 75.0
    assert summary["goal_minutes"] == 20

    by_inspector_response = client.get(
        f"{api_prefix}/productivity/by-inspector",
        params={
            "date_from": "2026-07-01",
            "date_to": "2026-07-31",
        },
    )
    log_api_response(
        "GET",
        f"{api_prefix}/productivity/by-inspector",
        by_inspector_response,
    )

    assert by_inspector_response.status_code == 200, by_inspector_response.text

    by_inspector = by_inspector_response.json()

    assert len(by_inspector) == 2

    ana_perez = next(
        item
        for item in by_inspector
        if item["inspector_name"] == "Ana Pérez"
    )
    luis_torres = next(
        item
        for item in by_inspector
        if item["inspector_name"] == "Luis Torres"
    )

    assert ana_perez["assigned_inspections"] == 2
    assert ana_perez["completed_reports"] == 2
    assert ana_perez["average_report_minutes"] == 15.0
    assert ana_perez["on_time_count"] == 2
    assert ana_perez["on_time_percentage"] == 100.0

    assert luis_torres["assigned_inspections"] == 2
    assert luis_torres["completed_reports"] == 2
    assert luis_torres["average_report_minutes"] == 22.5
    assert luis_torres["on_time_count"] == 1
    assert luis_torres["on_time_percentage"] == 50.0

    by_status_response = client.get(
        f"{api_prefix}/productivity/by-status",
        params={
            "date_from": "2026-07-01",
            "date_to": "2026-07-31",
        },
    )
    log_api_response(
        "GET",
        f"{api_prefix}/productivity/by-status",
        by_status_response,
    )

    assert by_status_response.status_code == 200, by_status_response.text

    by_status = by_status_response.json()

    assert by_status == [
        {
            "operational_status": "completed",
            "count": 4,
        },
    ]

    dashboard_response = client.get(
        f"{api_prefix}/productivity/dashboard",
        params={
            "date_from": "2026-07-01",
            "date_to": "2026-07-31",
            "inspector_name": "Ana Pérez",
            "operational_status": "completed",
        },
    )
    log_api_response(
        "GET",
        f"{api_prefix}/productivity/dashboard",
        dashboard_response,
    )

    assert dashboard_response.status_code == 200, dashboard_response.text

    dashboard = dashboard_response.json()

    assert dashboard["summary"]["total_inspections"] == 2
    assert dashboard["summary"]["completed_reports"] == 2
    assert dashboard["summary"]["average_report_minutes"] == 15.0
    assert dashboard["summary"]["on_time_count"] == 2
    assert dashboard["summary"]["on_time_percentage"] == 100.0
    assert dashboard["summary"]["goal_minutes"] == 20

    assert dashboard["by_inspector"] == [
        {
            "inspector_name": "Ana Pérez",
            "assigned_inspections": 2,
            "completed_reports": 2,
            "average_report_minutes": 15.0,
            "on_time_count": 2,
            "on_time_percentage": 100.0,
        },
    ]

    assert dashboard["by_status"] == [
        {
            "operational_status": "completed",
            "count": 2,
        },
    ]


def test_productivity_kpis_filter_records_by_date_range(client):
    inspection_july = create_inspection(
        client=client,
        code="INT-KPI-DATE-001",
        inspection_date="2026-07-10",
    )
    inspection_august = create_inspection(
        client=client,
        code="INT-KPI-DATE-002",
        inspection_date="2026-08-10",
    )

    create_completed_productivity(
        client=client,
        inspection_id=inspection_july["id"],
        inspector_name="Ana Pérez",
        scheduled_date="2026-07-10",
        duration_minutes=12,
    )
    create_completed_productivity(
        client=client,
        inspection_id=inspection_august["id"],
        inspector_name="Ana Pérez",
        scheduled_date="2026-08-10",
        duration_minutes=25,
    )

    july_summary_response = client.get(
        f"{api_prefix}/productivity/summary",
        params={
            "date_from": "2026-07-01",
            "date_to": "2026-07-31",
        },
    )
    log_api_response(
        "GET",
        f"{api_prefix}/productivity/summary?date_from=2026-07-01&date_to=2026-07-31",
        july_summary_response,
    )

    assert july_summary_response.status_code == 200, july_summary_response.text

    july_summary = july_summary_response.json()

    assert july_summary["total_inspections"] == 1
    assert july_summary["completed_reports"] == 1
    assert july_summary["average_report_minutes"] == 12.0
    assert july_summary["on_time_count"] == 1
    assert july_summary["on_time_percentage"] == 100.0

    august_summary_response = client.get(
        f"{api_prefix}/productivity/summary",
        params={
            "date_from": "2026-08-01",
            "date_to": "2026-08-31",
        },
    )

    assert august_summary_response.status_code == 200, august_summary_response.text

    august_summary = august_summary_response.json()

    assert august_summary["total_inspections"] == 1
    assert august_summary["completed_reports"] == 1
    assert august_summary["average_report_minutes"] == 25.0
    assert august_summary["on_time_count"] == 0
    assert august_summary["on_time_percentage"] == 0.0