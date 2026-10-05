import base64
import uuid
from datetime import datetime, timezone

import app.api.routes.evidences as evidences_routes


PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aF9sAAAAASUVORK5CYII="
)


def build_inspection_payload(code: str | None = None):
    unique_code = code or f"insp_evd_{uuid.uuid4().hex[:8]}"

    return {
        "code": unique_code,
        "client_name": "cliente_evidences",
        "equipment_type": "camion",
        "inspection_type": "operativa",
        "inspection_date": "2026-07-05",
        "location": "trujillo",
        "requested_by": "solicitante_evidences",
        "responsible_inspector_id": None,
        "status": "draft",
    }


def create_inspection_via_api(client, code: str | None = None):
    payload = build_inspection_payload(code)
    response = client.post("/api/v1/inspections", json=payload)
    assert response.status_code == 201, response.json()
    return response.json()


def create_evidence_via_api(client, inspection_id: int):
    files = {
        "file": ("evidencia_test.png", PNG_BYTES, "image/png"),
    }
    data = {
        "evidence_category": "placa_tecnica",
        "caption": "evidencia de prueba",
        "raw_label": "placa tecnica",
        "component_code": "plate",
        "axle_number": "1",
        "side": "left",
        "is_reference": "false",
    }

    response = client.post(
        f"/api/v1/inspections/{inspection_id}/evidences",
        files=files,
        data=data,
    )
    assert response.status_code == 201, response.json()
    return response.json()


def test_create_evidence_valid(client):
    inspection = create_inspection_via_api(client)

    files = {
        "file": ("evidencia_test.png", PNG_BYTES, "image/png"),
    }
    data = {
        "evidence_category": "placa_tecnica",
        "caption": "evidencia principal",
        "raw_label": "placa tecnica",
        "component_code": "plate",
        "axle_number": "1",
        "side": "left",
        "is_reference": "false",
    }

    response = client.post(
        f"/api/v1/inspections/{inspection['id']}/evidences",
        files=files,
        data=data,
    )

    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["inspection_id"] == inspection["id"]
    assert body["evidence_category"] == "placa_tecnica"


def test_list_evidences_by_inspection(client):
    inspection = create_inspection_via_api(client)
    create_evidence_via_api(client, inspection["id"])

    response = client.get(f"/api/v1/inspections/{inspection['id']}/evidences")

    assert response.status_code == 200, response.json()
    body = response.json()
    assert isinstance(body, list)
    assert len(body) >= 1
    assert body[0]["inspection_id"] == inspection["id"]


def test_run_ocr_from_evidence(client, monkeypatch):
    inspection = create_inspection_via_api(client)
    evidence = create_evidence_via_api(client, inspection["id"])

    def fake_process_evidence_ocr(db, evidence_id):
        record = evidences_routes.get_inspection(db, inspection["id"])
        assert record is not None

        evidence_record = next(
            item for item in record.evidences if item.id == evidence_id
        )
        evidence_record.ocr_extracted_text = "PLACA TECNICA 123"
        evidence_record.ocr_confidence = 98.7
        evidence_record.ocr_processed = True
        evidence_record.ocr_last_processed_at = datetime.now(timezone.utc)

        db.add(evidence_record)
        db.commit()
        db.refresh(evidence_record)
        return evidence_record

    monkeypatch.setattr(
        evidences_routes,
        "process_evidence_ocr",
        fake_process_evidence_ocr,
    )

    response = client.post(f"/api/v1/evidences/{evidence['id']}/ocr")

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["evidence_id"] == evidence["id"]
    assert body["ocr_extracted_text"] == "PLACA TECNICA 123"
    assert body["ocr_processed"] is True


def test_update_evidence_metadata(client):
    inspection = create_inspection_via_api(client)
    evidence = create_evidence_via_api(client, inspection["id"])

    payload = {
        "caption": "caption actualizada",
        "raw_label": "placa vehicular",
        "component_code": "plate",
        "axle_number": 2,
        "side": "right",
        "is_reference": True,
    }

    response = client.patch(
        f"/api/v1/evidences/{evidence['id']}",
        json=payload,
    )

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["id"] == evidence["id"]
    assert body["caption"] == "caption actualizada"
    assert body["is_reference"] is True