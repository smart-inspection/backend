import uuid

from app.db.models import InspectionProductivity


def build_inspection_payload(code: str | None = None):
    unique_code = code or f"insp_prod_{uuid.uuid4().hex[:8]}"

    return {
        "code": unique_code,
        "client_name": "cliente_prod",
        "equipment_type": "camion",
        "inspection_type": "operativa",
        "inspection_date": "2026-07-05",
        "location": "trujillo",
        "requested_by": "solicitante_prod",
        "responsible_inspector_id": None,
        "status": "draft",
    }


def create_inspection_via_api(client, code: str | None = None):
    payload = build_inspection_payload(code)
    response = client.post("/api/v1/inspections", json=payload)
    assert response.status_code == 201, response.json()
    return response.json()


def build_productivity_payload(inspection_id: int):
    return {
        "inspection_id": inspection_id,
        "inspector_name": "inspector_demo",
        "scheduled_date": "2026-07-05",
        "report_started_at": None,
        "report_finished_at": None,
        "operational_status": "pending",
        "met_goal": None,
    }


def ensure_no_productivity_record(db_session, inspection_id: int):
    existing = (
        db_session.query(InspectionProductivity)
        .filter(InspectionProductivity.inspection_id == inspection_id)
        .first()
    )
    if existing:
        db_session.delete(existing)
        db_session.commit()


def create_productivity_via_api(client, db_session, inspection_id: int):
    ensure_no_productivity_record(db_session, inspection_id)
    response = client.post(
        "/api/v1/productivity",
        json=build_productivity_payload(inspection_id),
    )
    assert response.status_code == 201, response.json()
    return response.json()


def test_create_productivity(client, db_session):
    inspection = create_inspection_via_api(client)

    response = client.post(
        "/api/v1/productivity",
        json=build_productivity_payload(inspection["id"]),
    )

    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["inspection_id"] == inspection["id"]
    assert body["inspector_name"] == "inspector_demo"
    assert body["operational_status"] == "pending"


def test_get_productivity_by_inspection(client, db_session):
    inspection = create_inspection_via_api(client)
    productivity = create_productivity_via_api(client, db_session, inspection["id"])

    response = client.get(f"/api/v1/productivity/inspection/{inspection['id']}")

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["id"] == productivity["id"]
    assert body["inspection_id"] == inspection["id"]


def test_update_productivity_by_inspection(client, db_session):
    inspection = create_inspection_via_api(client)
    create_productivity_via_api(client, db_session, inspection["id"])

    payload = {
        "inspector_name": "inspector_actualizado",
        "scheduled_date": "2026-07-06",
        "operational_status": "in_progress",
        "met_goal": False,
    }

    response = client.put(
        f"/api/v1/productivity/inspection/{inspection['id']}",
        json=payload,
    )

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["inspection_id"] == inspection["id"]
    assert body["inspector_name"] == "inspector_actualizado"
    assert body["operational_status"] == "in_progress"


def test_start_productivity(client, db_session):
    inspection = create_inspection_via_api(client)
    create_productivity_via_api(client, db_session, inspection["id"])

    response = client.patch(
        f"/api/v1/productivity/inspection/{inspection['id']}/start",
        json={"report_started_at": "2026-07-05T20:00:00"},
    )

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["inspection_id"] == inspection["id"]
    assert body["report_started_at"] is not None


def test_finish_productivity(client, db_session):
    inspection = create_inspection_via_api(client)
    create_productivity_via_api(client, db_session, inspection["id"])

    start_response = client.patch(
        f"/api/v1/productivity/inspection/{inspection['id']}/start",
        json={"report_started_at": "2026-07-05T20:00:00"},
    )
    assert start_response.status_code == 200, start_response.json()

    response = client.patch(
        f"/api/v1/productivity/inspection/{inspection['id']}/finish",
        json={
            "report_finished_at": "2026-07-05T20:18:00",
            "operational_status": "completed",
        },
    )

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["inspection_id"] == inspection["id"]
    assert body["report_finished_at"] is not None
    assert body["operational_status"] == "completed"
    assert body["duration_minutes"] == 18.0
    assert body["met_goal"] is True


def test_productivity_summary(client, db_session):
    inspection = create_inspection_via_api(client)
    create_productivity_via_api(client, db_session, inspection["id"])

    start_response = client.patch(
        f"/api/v1/productivity/inspection/{inspection['id']}/start",
        json={"report_started_at": "2026-07-05T20:00:00"},
    )
    assert start_response.status_code == 200, start_response.json()

    finish_response = client.patch(
        f"/api/v1/productivity/inspection/{inspection['id']}/finish",
        json={
            "report_finished_at": "2026-07-05T20:15:00",
            "operational_status": "completed",
        },
    )
    assert finish_response.status_code == 200, finish_response.json()

    response = client.get(
        "/api/v1/productivity/summary",
        params={
            "date_from": "2026-07-01",
            "date_to": "2026-07-31",
            "inspector_name": "inspector_demo",
            "operational_status": "completed",
        },
    )

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body is not None


def test_productivity_by_inspector(client, db_session):
    inspection = create_inspection_via_api(client)
    create_productivity_via_api(client, db_session, inspection["id"])

    response = client.get(
        "/api/v1/productivity/by-inspector",
        params={
            "date_from": "2026-07-01",
            "date_to": "2026-07-31",
            "inspector_name": "inspector_demo",
            "operational_status": "pending",
        },
    )

    assert response.status_code == 200, response.json()
    body = response.json()
    assert isinstance(body, list)


def test_productivity_by_status(client, db_session):
    inspection = create_inspection_via_api(client)
    create_productivity_via_api(client, db_session, inspection["id"])

    response = client.get(
        "/api/v1/productivity/by-status",
        params={
            "date_from": "2026-07-01",
            "date_to": "2026-07-31",
            "inspector_name": "inspector_demo",
        },
    )

    assert response.status_code == 200, response.json()
    body = response.json()
    assert isinstance(body, list)


def test_productivity_dashboard(client, db_session):
    inspection = create_inspection_via_api(client)
    create_productivity_via_api(client, db_session, inspection["id"])

    response = client.get(
        "/api/v1/productivity/dashboard",
        params={
            "date_from": "2026-07-01",
            "date_to": "2026-07-31",
            "inspector_name": "inspector_demo",
            "operational_status": "pending",
        },
    )

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body is not None