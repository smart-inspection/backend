import base64
import uuid

import app.api.routes.ocr as ocr_routes


PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aF9sAAAAASUVORK5CYII="
)


def build_inspection_payload(code: str | None = None):
    unique_code = code or f"insp_ocr_{uuid.uuid4().hex[:8]}"

    return {
        "code": unique_code,
        "client_name": "cliente_ocr",
        "equipment_type": "camion",
        "inspection_type": "operativa",
        "inspection_date": "2026-07-05",
        "location": "trujillo",
        "requested_by": "solicitante_ocr",
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
        "file": ("ocr_test.png", PNG_BYTES, "image/png"),
    }
    data = {
        "evidence_category": "placa_tecnica",
        "caption": "evidencia ocr",
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


def test_extract_text_from_evidence(client, monkeypatch):
    inspection = create_inspection_via_api(client)
    evidence = create_evidence_via_api(client, inspection["id"])

    def fake_extract_text_from_evidence(db, evidence_id):
        assert evidence_id == evidence["id"]
        return {
            "evidence_id": evidence_id,
            "evidence_category": "placa_tecnica",
            "file_path": "uploads/test/ocr_test.png",
            "extracted_text": "PLACA ABC123",
            "confidence": 97.4,
        }

    monkeypatch.setattr(
        ocr_routes,
        "extract_text_from_evidence",
        fake_extract_text_from_evidence,
    )

    response = client.post(f"/api/v1/ocr/evidences/{evidence['id']}/extract")

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["evidence_id"] == evidence["id"]
    assert body["extracted_text"] == "PLACA ABC123"


def test_validate_ocr_of_inspection(client, monkeypatch):
    inspection = create_inspection_via_api(client)
    create_evidence_via_api(client, inspection["id"])

    def fake_validate_inspection_ocr(db, inspection_id):
        assert inspection_id == inspection["id"]
        return {
            "inspection_id": inspection_id,
            "processed_evidences": 1,
            "aggregated_text": "PLACA ABC123 MARCA DEMO",
            "summary": {
                "matched": 1,
                "mismatched": 0,
                "not_found": 0,
                "average_confidence": 96.8,
            },
            "results": [
                {
                    "field_id": 1,
                    "field_key": "placa",
                    "field_label": "Placa",
                    "manual_value": "ABC123",
                    "ocr_value": "ABC123",
                    "final_value": "ABC123",
                    "validation_status": "matched",
                    "validation_message": "coincidencia exacta",
                    "confidence": 96.8,
                }
            ],
        }

    monkeypatch.setattr(
        ocr_routes,
        "validate_inspection_ocr",
        fake_validate_inspection_ocr,
    )

    response = client.post(f"/api/v1/ocr/inspections/{inspection['id']}/validate")

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["inspection_id"] == inspection["id"]
    assert body["processed_evidences"] == 1
    assert len(body["results"]) == 1