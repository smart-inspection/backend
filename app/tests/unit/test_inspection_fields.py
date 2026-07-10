import uuid


def build_inspection_payload(code: str | None = None):
    unique_code = code or f"insp_fld_{uuid.uuid4().hex[:8]}"

    return {
        "code": unique_code,
        "client_name": "cliente_fields",
        "equipment_type": "camion",
        "inspection_type": "operativa",
        "inspection_date": "2026-07-05",
        "location": "trujillo",
        "requested_by": "solicitante_fields",
        "responsible_inspector_id": None,
        "status": "draft",
    }


def create_inspection_via_api(client, code: str | None = None):
    payload = build_inspection_payload(code)
    response = client.post("/api/v1/inspections", json=payload)
    assert response.status_code == 201, response.json()
    return response.json()


def build_field_payload():
    return {
        "field_key": f"placa_{uuid.uuid4().hex[:6]}",
        "field_label": "Placa",
        "field_group": "identificacion",
        "expected_type": "string",
        "manual_value": "ABC-123",
        "ocr_value": None,
        "final_value": "ABC-123",
        "validation_status": "pending",
        "validation_message": None,
        "confidence": None,
    }


def create_field_via_api(client, inspection_id: int):
    payload = build_field_payload()
    response = client.post(
        f"/api/v1/inspections/{inspection_id}/fields",
        json=payload,
    )
    assert response.status_code == 201, response.json()
    return response.json()


def test_create_inspection_field(client):
    inspection = create_inspection_via_api(client)

    response = client.post(
        f"/api/v1/inspections/{inspection['id']}/fields",
        json=build_field_payload(),
    )

    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["inspection_id"] == inspection["id"]
    assert body["field_label"] == "Placa"


def test_list_inspection_fields(client):
    inspection = create_inspection_via_api(client)
    create_field_via_api(client, inspection["id"])

    response = client.get(f"/api/v1/inspections/{inspection['id']}/fields")

    assert response.status_code == 200, response.json()
    body = response.json()
    assert isinstance(body, list)
    assert len(body) >= 1
    assert body[0]["inspection_id"] == inspection["id"]


def test_update_inspection_field_patch(client):
    inspection = create_inspection_via_api(client)
    field = create_field_via_api(client, inspection["id"])

    payload = {
        "manual_value": "XYZ-999",
        "final_value": "XYZ-999",
        "validation_status": "matched",
        "validation_message": "actualizado con patch",
    }

    response = client.patch(
        f"/api/v1/inspections/{inspection['id']}/fields/{field['id']}",
        json=payload,
    )

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["id"] == field["id"]
    assert body["manual_value"] == "XYZ-999"
    assert body["final_value"] == "XYZ-999"


def test_update_inspection_field_put(client):
    inspection = create_inspection_via_api(client)
    field = create_field_via_api(client, inspection["id"])

    payload = {
        "field_key": field["field_key"],
        "field_label": "Placa actualizada",
        "field_group": "identificacion",
        "expected_type": "string",
        "manual_value": "LMN-456",
        "ocr_value": "LMN-456",
        "final_value": "LMN-456",
        "validation_status": "matched",
        "validation_message": "actualizado con put",
        "confidence": 98.5,
    }

    response = client.put(
        f"/api/v1/inspections/{inspection['id']}/fields/{field['id']}",
        json=payload,
    )

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["id"] == field["id"]
    assert body["field_label"] == "Placa actualizada"
    assert body["final_value"] == "LMN-456"