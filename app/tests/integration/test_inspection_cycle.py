from datetime import datetime, timedelta, timezone

from app.db.models import Evidence, Transcription

from conftest import log_api_response


api_prefix = "/api/v1"


def create_ocr_stub(monkeypatch):
    def fake_extract_text_from_evidence(db, evidence_id):
        evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()

        if not evidence:
            return None

        evidence.ocr_extracted_text = "PLACA ABC-123"
        evidence.ocr_confidence = 0.99
        evidence.ocr_processed = True
        evidence.ocr_last_processed_at = datetime.now(timezone.utc)

        db.add(evidence)
        db.commit()
        db.refresh(evidence)

        return {
            "evidence_id": evidence.id,
            "evidence_category": evidence.evidence_category,
            "file_path": evidence.file_path,
            "extracted_text": evidence.ocr_extracted_text,
            "confidence": float(evidence.ocr_confidence),
        }

    monkeypatch.setattr(
        "app.api.routes.ocr.extract_text_from_evidence",
        fake_extract_text_from_evidence,
    )


def create_transcription_stub(monkeypatch):
    def fake_create_and_process_transcription(db, payload):
        transcription = Transcription(
            inspection_id=payload.inspection_id,
            evidence_id=payload.evidence_id,
            source_file_path=payload.source_file_path,
            language=payload.language,
            model_name=payload.model_name,
            raw_text="Observación de prueba registrada durante la inspección.",
            final_text="Observación de prueba registrada durante la inspección.",
            confidence=0.98,
            processed=True,
            edited_manually=False,
        )

        db.add(transcription)
        db.commit()
        db.refresh(transcription)

        return transcription

    monkeypatch.setattr(
        "app.api.routes.transcription.create_and_process_transcription",
        fake_create_and_process_transcription,
    )


def test_inspection_cycle_generates_finalized_report_and_productivity(
    client,
    monkeypatch,
):
    create_ocr_stub(monkeypatch)
    create_transcription_stub(monkeypatch)

    inspection_payload = {
        "code": "INT-FLOW-001",
        "client_name": "Empresa Integración S.A.C.",
        "equipment_type": "Camión",
        "inspection_type": "Inspección técnica",
        "inspection_date": "2026-07-10",
        "location": "Trujillo",
        "requested_by": "Cliente de integración",
        "status": "draft",
    }

    inspection_response = client.post(
        f"{api_prefix}/inspections",
        json=inspection_payload,
    )
    log_api_response(
        "POST",
        f"{api_prefix}/inspections",
        inspection_response,
    )

    assert inspection_response.status_code == 201

    inspection = inspection_response.json()
    inspection_id = inspection["id"]

    assert inspection["code"] == inspection_payload["code"]
    assert inspection["status"] == "draft"

    field_payload = {
        "field_key": "vehicle_plate",
        "field_label": "Placa del vehículo",
        "field_group": "identification",
        "expected_type": "text",
        "manual_value": "ABC-123",
        "final_value": "ABC-123",
        "validation_status": "pending",
    }

    field_response = client.post(
        f"{api_prefix}/inspections/{inspection_id}/fields",
        json=field_payload,
    )
    log_api_response(
        "POST",
        f"{api_prefix}/inspections/{inspection_id}/fields",
        field_response,
    )

    assert field_response.status_code == 201

    field = field_response.json()

    assert field["inspection_id"] == inspection_id
    assert field["manual_value"] == "ABC-123"

    evidence_response = client.post(
        f"{api_prefix}/inspections/{inspection_id}/evidences",
        files={
            "file": (
                "placa_test.png",
                b"fake_image_content_for_integration_test",
                "image/png",
            ),
        },
        data={
            "evidence_category": "placa",
            "caption": "Evidencia de placa para prueba de integración",
            "raw_label": "placa",
        },
    )
    log_api_response(
        "POST",
        f"{api_prefix}/inspections/{inspection_id}/evidences",
        evidence_response,
    )

    assert evidence_response.status_code == 201

    evidence = evidence_response.json()
    evidence_id = evidence["id"]

    assert evidence["inspection_id"] == inspection_id
    assert evidence["evidence_category"] == "placa"

    ocr_response = client.post(
        f"{api_prefix}/ocr/evidences/{evidence_id}/extract",
    )
    log_api_response(
        "POST",
        f"{api_prefix}/ocr/evidences/{evidence_id}/extract",
        ocr_response,
    )

    assert ocr_response.status_code == 200

    ocr_result = ocr_response.json()

    assert ocr_result["evidence_id"] == evidence_id
    assert ocr_result["extracted_text"] == "PLACA ABC-123"
    assert ocr_result["confidence"] == 0.99

    ocr_validation_response = client.post(
        f"{api_prefix}/ocr/inspections/{inspection_id}/validate",
    )
    log_api_response(
        "POST",
        f"{api_prefix}/ocr/inspections/{inspection_id}/validate",
        ocr_validation_response,
    )

    assert ocr_validation_response.status_code == 200

    ocr_validation = ocr_validation_response.json()

    assert ocr_validation["inspection_id"] == inspection_id
    assert ocr_validation["processed_evidences"] == 1

    transcription_payload = {
        "inspection_id": inspection_id,
        "evidence_id": evidence_id,
        "source_file_path": evidence["file_path"],
        "language": "es",
        "model_name": "integration_test_stub",
    }

    transcription_response = client.post(
        f"{api_prefix}/transcription",
        json=transcription_payload,
    )
    log_api_response(
        "POST",
        f"{api_prefix}/transcription",
        transcription_response,
    )

    assert transcription_response.status_code == 201

    transcription = transcription_response.json()

    assert transcription["inspection_id"] == inspection_id
    assert transcription["evidence_id"] == evidence_id
    assert transcription["processed"] is True
    assert transcription["final_text"] is not None

    report_response = client.post(
        f"{api_prefix}/report-drafts/generate/{inspection_id}",
        json={"template_version": "integration-v1"},
    )
    log_api_response(
        "POST",
        f"{api_prefix}/report-drafts/generate/{inspection_id}",
        report_response,
    )

    assert report_response.status_code == 201, (
        f"Error al generar borrador: "
        f"status_code={report_response.status_code}, "
        f"response={report_response.text}"
    )

    report_draft = report_response.json()
    report_draft_id = report_draft["id"]

    assert report_draft["inspection_id"] == inspection_id
    assert report_draft["generated_text"]
    assert report_draft["template_version"] == "integration-v1"

    report_in_review_response = client.patch(
        f"{api_prefix}/reports/{report_draft_id}/status",
        json={
            "status": "in_review",
            "notes": "Revisión completada durante prueba de integración.",
        },
    )
    log_api_response(
        "PATCH",
        f"{api_prefix}/reports/{report_draft_id}/status",
        report_in_review_response,
    )

    assert report_in_review_response.status_code == 200
    assert report_in_review_response.json()["status"] == "in_review"

    productivity_start_time = datetime.now(timezone.utc) - timedelta(minutes=15)

    productivity_start_response = client.patch(
        f"{api_prefix}/productivity/inspection/{inspection_id}/start",
        json={"report_started_at": productivity_start_time.isoformat()},
    )
    log_api_response(
        "PATCH",
        f"{api_prefix}/productivity/inspection/{inspection_id}/start",
        productivity_start_response,
    )

    report_finalized_response = client.patch(
        f"{api_prefix}/reports/{report_draft_id}/status",
        json={
            "status": "finalized",
            "notes": "Informe finalizado durante prueba de integración.",
        },
    )
    log_api_response(
        "PATCH",
        f"{api_prefix}/reports/{report_draft_id}/status",
        report_finalized_response,
    )

    assert report_finalized_response.status_code == 200
    assert report_finalized_response.json()["status"] == "finalized"

    assert productivity_start_response.status_code == 200

    productivity_detail_response = client.get(
        f"{api_prefix}/productivity/inspection/{inspection_id}",
    )
    log_api_response(
        "GET",
        f"{api_prefix}/productivity/inspection/{inspection_id}",
        productivity_detail_response,
    )

    assert productivity_detail_response.status_code == 200, (
        f"Error al consultar productividad: "
        f"status_code={productivity_detail_response.status_code}, "
        f"response={productivity_detail_response.text}"
    )

    productivity = productivity_detail_response.json()

    assert productivity["inspection_id"] == inspection_id
    assert productivity["operational_status"] == "completed"
    assert productivity["duration_minutes"] is not None
    assert productivity["duration_minutes"] <= 20
    assert productivity["met_goal"] is True