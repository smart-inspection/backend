import uuid

import app.api.routes.report_draft as report_draft_routes
import app.api.routes.llm_report as llm_report_routes
import app.api.routes.report_export as report_export_routes
from app.db.models import ReportDraft
from pathlib import Path


def build_inspection_payload(code: str | None = None):
    unique_code = code or f"insp_drf_{uuid.uuid4().hex[:8]}"

    return {
        "code": unique_code,
        "client_name": "cliente_report_drafts",
        "equipment_type": "camion",
        "inspection_type": "operativa",
        "inspection_date": "2026-07-05",
        "location": "trujillo",
        "requested_by": "solicitante_report_drafts",
        "responsible_inspector_id": None,
        "status": "draft",
    }


def create_inspection_via_api(client, code: str | None = None):
    payload = build_inspection_payload(code)
    response = client.post("/api/v1/inspections", json=payload)
    assert response.status_code == 201, response.json()
    return response.json()


def create_report_draft_record(db_session, inspection_id: int):
    draft = ReportDraft(
        inspection_id=inspection_id,
        title=f"Borrador de informe - Inspección {inspection_id}",
        template_version="v1",
        status="draft",
        generated_text="contenido generado base",
        edited_text=None,
        source_snapshot={"inspection_id": inspection_id},
        generation_time_ms=150,
        last_action="draft_generated",
    )
    db_session.add(draft)
    db_session.commit()
    db_session.refresh(draft)
    return draft


def test_generate_base_draft(client, db_session, monkeypatch):
    inspection = create_inspection_via_api(client)

    def fake_generate_report_draft(
        db,
        inspection_id: int,
        template_version: str = "v1",
        user_id: int | None = None,
        user_name: str | None = None,
    ):
        draft = ReportDraft(
            inspection_id=inspection_id,
            title=f"Borrador de informe - Inspección {inspection_id}",
            template_version=template_version,
            status="draft",
            generated_text="borrador generado automáticamente",
            edited_text=None,
            source_snapshot={"inspection_id": inspection_id, "template_version": template_version},
            generation_time_ms=120,
            last_action="draft_generated",
        )
        db.add(draft)
        db.commit()
        db.refresh(draft)
        return draft

    monkeypatch.setattr(
        report_draft_routes,
        "generate_report_draft",
        fake_generate_report_draft,
    )

    response = client.post(
        f"/api/v1/report-drafts/generate/{inspection['id']}",
        json={"template_version": "v1"},
    )

    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["inspection_id"] == inspection["id"]
    assert body["template_version"] == "v1"
    assert body["generated_text"] == "borrador generado automáticamente"


def test_list_drafts_by_inspection(client, db_session):
    inspection = create_inspection_via_api(client)
    create_report_draft_record(db_session, inspection["id"])

    response = client.get(f"/api/v1/report-drafts/inspection/{inspection['id']}")

    assert response.status_code == 200, response.json()
    body = response.json()
    assert isinstance(body, list)
    assert len(body) >= 1
    assert body[0]["inspection_id"] == inspection["id"]


def test_get_draft_by_id(client, db_session):
    inspection = create_inspection_via_api(client)
    draft = create_report_draft_record(db_session, inspection["id"])

    response = client.get(f"/api/v1/report-drafts/{draft.id}")

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["id"] == draft.id
    assert body["inspection_id"] == inspection["id"]


def test_update_edited_draft(client, db_session):
    inspection = create_inspection_via_api(client)
    draft = create_report_draft_record(db_session, inspection["id"])

    response = client.put(
        f"/api/v1/report-drafts/{draft.id}",
        json={
            "edited_text": "texto final editado manualmente",
            "status": "edited",
        },
    )

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["id"] == draft.id
    assert body["edited_text"] == "texto final editado manualmente"


def build_inspection_payload(code: str | None = None):
    unique_code = code or f"insp_llm_{uuid.uuid4().hex[:8]}"

    return {
        "code": unique_code,
        "client_name": "cliente_llm_report",
        "equipment_type": "camion",
        "inspection_type": "operativa",
        "inspection_date": "2026-07-05",
        "location": "trujillo",
        "requested_by": "solicitante_llm_report",
        "responsible_inspector_id": None,
        "status": "draft",
    }


def create_inspection_via_api(client, code: str | None = None):
    payload = build_inspection_payload(code)
    response = client.post("/api/v1/inspections", json=payload)
    assert response.status_code == 201, response.json()
    return response.json()


def test_generate_report_with_llm(client, monkeypatch):
    inspection = create_inspection_via_api(client)

    def fake_generate_llm_report_draft(db, inspection_id: int, template_version: str):
        draft = ReportDraft(
            inspection_id=inspection_id,
            title=f"Informe LLM - Inspección {inspection_id}",
            template_version=template_version,
            status="draft",
            generated_text="informe generado con llm",
            edited_text=None,
            source_snapshot={
                "inspection_id": inspection_id,
                "provider": "ollama",
                "template_version": template_version,
            },
            generation_time_ms=320,
            last_action="draft_generated_llm",
        )
        db.add(draft)
        db.commit()
        db.refresh(draft)
        return draft

    monkeypatch.setattr(
        llm_report_routes,
        "generate_llm_report_draft",
        fake_generate_llm_report_draft,
    )

    response = client.post(
        f"/api/v1/llm-report/generate/{inspection['id']}",
        json={"template_version": "llama3-v1"},
    )

    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["inspection_id"] == inspection["id"]
    assert body["template_version"] == "llama3-v1"
    assert body["generated_text"] == "informe generado con llm"


def build_inspection_payload(code: str | None = None):
    unique_code = code or f"insp_exp_{uuid.uuid4().hex[:8]}"

    return {
        "code": unique_code,
        "client_name": "cliente_report_export",
        "equipment_type": "camion",
        "inspection_type": "operativa",
        "inspection_date": "2026-07-05",
        "location": "trujillo",
        "requested_by": "solicitante_report_export",
        "responsible_inspector_id": None,
        "status": "draft",
    }


def create_inspection_via_api(client, code: str | None = None):
    payload = build_inspection_payload(code)
    response = client.post("/api/v1/inspections", json=payload)
    assert response.status_code == 201, response.json()
    return response.json()


def create_report_draft_record(db_session, inspection_id: int):
    draft = ReportDraft(
        inspection_id=inspection_id,
        title=f"Borrador exportable - Inspección {inspection_id}",
        template_version="v1",
        status="draft",
        generated_text="contenido exportable",
        edited_text=None,
        source_snapshot={"inspection_id": inspection_id},
        generation_time_ms=100,
        last_action="draft_generated",
    )
    db_session.add(draft)
    db_session.commit()
    db_session.refresh(draft)
    return draft


def test_export_draft_to_docx(client, db_session, tmp_path, monkeypatch):
    inspection = create_inspection_via_api(client)
    draft = create_report_draft_record(db_session, inspection["id"])

    docx_path = tmp_path / "draft_test.docx"
    docx_path.write_bytes(b"fake-docx-content")

    def fake_export_report_docx(db, draft_id: int):
        assert draft_id == draft.id
        return str(docx_path)

    monkeypatch.setattr(
        report_export_routes,
        "export_report_docx",
        fake_export_report_docx,
    )

    response = client.get(f"/api/v1/report-export/docx/{draft.id}")

    assert response.status_code == 200
    assert (
        response.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


def test_export_draft_to_pdf(client, db_session, tmp_path, monkeypatch):
    inspection = create_inspection_via_api(client)
    draft = create_report_draft_record(db_session, inspection["id"])

    pdf_path = tmp_path / "draft_test.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake-pdf-content")

    def fake_export_report_pdf(db, draft_id: int):
        assert draft_id == draft.id
        return str(pdf_path)

    monkeypatch.setattr(
        report_export_routes,
        "export_report_pdf",
        fake_export_report_pdf,
    )

    response = client.get(f"/api/v1/report-export/pdf/{draft.id}")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"


def build_inspection_payload(code: str | None = None):
    unique_code = code or f"insp_sts_{uuid.uuid4().hex[:8]}"

    return {
        "code": unique_code,
        "client_name": "cliente_report_status",
        "equipment_type": "camion",
        "inspection_type": "operativa",
        "inspection_date": "2026-07-05",
        "location": "trujillo",
        "requested_by": "solicitante_report_status",
        "responsible_inspector_id": None,
        "status": "draft",
    }


def create_inspection_via_api(client, code: str | None = None):
    payload = build_inspection_payload(code)
    response = client.post("/api/v1/inspections", json=payload)
    assert response.status_code == 201, response.json()
    return response.json()


def create_report_draft_record(db_session, inspection_id: int):
    draft = ReportDraft(
        inspection_id=inspection_id,
        title=f"Borrador con estado - Inspección {inspection_id}",
        template_version="v1",
        status="draft",
        generated_text="contenido inicial",
        edited_text=None,
        source_snapshot={"inspection_id": inspection_id},
        generation_time_ms=80,
        last_action="draft_generated",
    )
    db_session.add(draft)
    db_session.commit()
    db_session.refresh(draft)
    return draft


def test_get_current_report_status(client, db_session):
    inspection = create_inspection_via_api(client)
    draft = create_report_draft_record(db_session, inspection["id"])

    response = client.get(f"/api/v1/reports/{draft.id}/status")

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["report_draft_id"] == draft.id
    assert body["status"] == "draft"


def test_change_report_status(client, db_session):
    inspection = create_inspection_via_api(client)
    draft = create_report_draft_record(db_session, inspection["id"])

    response = client.patch(
        f"/api/v1/reports/{draft.id}/status",
        json={
            "status": "in_review",
            "notes": "pasa a revisión técnica",
        },
    )

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["report_draft_id"] == draft.id
    assert body["status"] == "in_review"
    assert body["last_action"] == "status_changed"


def test_list_report_status_history(client, db_session):
    inspection = create_inspection_via_api(client)
    draft = create_report_draft_record(db_session, inspection["id"])

    update_response = client.patch(
        f"/api/v1/reports/{draft.id}/status",
        json={
            "status": "in_review",
            "notes": "historial inicial",
        },
    )
    assert update_response.status_code == 200, update_response.json()

    response = client.get(f"/api/v1/reports/{draft.id}/history?limit=50")

    assert response.status_code == 200, response.json()
    body = response.json()
    assert isinstance(body, list)
    assert len(body) >= 1
    assert body[0]["report_draft_id"] == draft.id