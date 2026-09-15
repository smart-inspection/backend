import base64
import uuid

import app.api.routes.transcription as transcription_routes
from app.db.models import Transcription


PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aF9sAAAAASUVORK5CYII="
)


def build_inspection_payload(code: str | None = None):
    unique_code = code or f"insp_trn_{uuid.uuid4().hex[:8]}"

    return {
        "code": unique_code,
        "client_name": "cliente_transcription",
        "equipment_type": "camion",
        "inspection_type": "operativa",
        "inspection_date": "2026-07-05",
        "location": "trujillo",
        "requested_by": "solicitante_transcription",
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
        "file": ("transcription_ref.png", PNG_BYTES, "image/png"),
    }
    data = {
        "evidence_category": "audio_referencia",
        "caption": "evidencia asociada",
        "raw_label": "audio referencia",
        "component_code": "audio",
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


def create_transcription_via_api(client, inspection_id: int, evidence_id: int, monkeypatch):
    def fake_create_and_process_transcription(db, payload):
        transcription = Transcription(
            inspection_id=payload.inspection_id,
            evidence_id=payload.evidence_id,
            source_file_path=payload.source_file_path,
            language=payload.language,
            model_name=payload.model_name,
            raw_text="texto transcrito de prueba",
            final_text="texto transcrito de prueba",
            confidence=91.5,
            processed=True,
            edited_manually=False,
        )
        db.add(transcription)
        db.commit()
        db.refresh(transcription)
        return transcription

    monkeypatch.setattr(
        transcription_routes,
        "create_and_process_transcription",
        fake_create_and_process_transcription,
    )

    payload = {
        "inspection_id": inspection_id,
        "evidence_id": evidence_id,
        "source_file_path": "uploads/test/audio_demo.wav",
        "language": "es",
        "model_name": "base",
    }

    response = client.post("/api/v1/transcription", json=payload)
    assert response.status_code == 201, response.json()
    return response.json()


def test_create_and_process_transcription(client, monkeypatch):
    inspection = create_inspection_via_api(client)
    evidence = create_evidence_via_api(client, inspection["id"])

    transcription = create_transcription_via_api(
        client,
        inspection["id"],
        evidence["id"],
        monkeypatch,
    )

    assert transcription["inspection_id"] == inspection["id"]
    assert transcription["evidence_id"] == evidence["id"]
    assert transcription["processed"] is True


def test_list_transcriptions_by_inspection(client, monkeypatch):
    inspection = create_inspection_via_api(client)
    evidence = create_evidence_via_api(client, inspection["id"])

    create_transcription_via_api(
        client,
        inspection["id"],
        evidence["id"],
        monkeypatch,
    )

    response = client.get(f"/api/v1/transcription/inspection/{inspection['id']}")

    assert response.status_code == 200, response.json()
    body = response.json()
    assert isinstance(body, list)
    assert len(body) >= 1
    assert body[0]["inspection_id"] == inspection["id"]


def test_get_transcription_by_id(client, monkeypatch):
    inspection = create_inspection_via_api(client)
    evidence = create_evidence_via_api(client, inspection["id"])

    transcription = create_transcription_via_api(
        client,
        inspection["id"],
        evidence["id"],
        monkeypatch,
    )

    response = client.get(f"/api/v1/transcription/{transcription['id']}")

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["id"] == transcription["id"]
    assert body["inspection_id"] == inspection["id"]


def test_update_final_text_of_transcription(client, monkeypatch):
    inspection = create_inspection_via_api(client)
    evidence = create_evidence_via_api(client, inspection["id"])

    transcription = create_transcription_via_api(
        client,
        inspection["id"],
        evidence["id"],
        monkeypatch,
    )

    payload = {
        "final_text": "texto final corregido manualmente",
    }

    response = client.put(
        f"/api/v1/transcription/{transcription['id']}",
        json=payload,
    )

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["id"] == transcription["id"]
    assert body["final_text"] == "texto final corregido manualmente"
    assert body["edited_manually"] is True