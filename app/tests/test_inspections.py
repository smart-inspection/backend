import uuid


def build_inspection_payload(code: str | None = None):
    unique_code = code or f"insp_test_{uuid.uuid4().hex[:8]}"

    return {
        "code": unique_code,
        "client_name": "cliente_demo",
        "equipment_type": "tractor",
        "inspection_type": "tecnica",
        "inspection_date": "2026-07-05",
        "location": "trujillo",
        "requested_by": "solicitante_demo",
        "responsible_inspector_id": None,
        "status": "draft",
    }


def test_create_inspection(client):
    payload = build_inspection_payload()

    response = client.post("/api/v1/inspections", json=payload)

    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["code"] == payload["code"]
    assert body["client_name"] == payload["client_name"]


def test_list_inspections(client):
    payload = build_inspection_payload()
    create_response = client.post("/api/v1/inspections", json=payload)

    assert create_response.status_code == 201, create_response.json()

    response = client.get("/api/v1/inspections")

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert any(item["code"] == payload["code"] for item in body)


def test_get_inspection_by_id(client):
    payload = build_inspection_payload()
    create_response = client.post("/api/v1/inspections", json=payload)

    assert create_response.status_code == 201, create_response.json()
    created = create_response.json()

    response = client.get(f"/api/v1/inspections/{created['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_inspection_not_found(client):
    response = client.get("/api/v1/inspections/999999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Inspection not found"