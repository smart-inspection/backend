import uuid

import app.api.routes.report_draft as report_draft_routes
import app.api.routes.llm_report as llm_report_routes
import app.api.routes.report_export as report_export_routes
from app.db.models import InspectionProductivity, ReportDraft, ReportStatusLog, User
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


INSPECTION_ACCESS_DENIED_DETAIL = (
    "No tienes autorización para acceder o modificar esta inspección."
)
FINALIZE_FORBIDDEN_DETAIL = (
    "Solo un administrador puede aprobar y finalizar formalmente una inspección."
)
REOPEN_FORBIDDEN_DETAIL = (
    "Solo un administrador puede reabrir una inspección finalizada."
)
REPORT_DRAFT_NOT_FOUND_DETAIL = (
    "No se encontró un borrador de informe asociado a esta inspección. "
    "Debe generar un borrador antes de gestionar su estado."
)


def create_user_record(db_session, role: str) -> User:
    user = User(
        full_name=f"{role}_{uuid.uuid4().hex[:6]}",
        email=f"{uuid.uuid4().hex[:8]}@test.local",
        password_hash="x",
        role=role,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    db_session.expunge(user)
    return user


def create_assigned_inspection(client, inspector_id: int | None):
    payload = build_inspection_payload()
    payload["responsible_inspector_id"] = inspector_id
    response = client.post("/api/v1/inspections", json=payload)
    assert response.status_code == 201, response.json()
    return response.json()


def status_transition_url(inspection_id: int) -> str:
    return f"/api/v1/inspections/{inspection_id}/status-transition"


def get_productivity_record(db_session, inspection_id: int) -> InspectionProductivity:
    db_session.expire_all()
    return (
        db_session.query(InspectionProductivity)
        .filter(InspectionProductivity.inspection_id == inspection_id)
        .one()
    )


def get_draft_status(db_session, draft_id: int) -> str:
    db_session.expire_all()
    return db_session.query(ReportDraft).filter(ReportDraft.id == draft_id).one().status


def test_inspector_lists_only_assigned_inspections(client, db_session, auth_as):
    inspector_a = create_user_record(db_session, "inspector")
    inspector_b = create_user_record(db_session, "inspector")
    own_1 = create_assigned_inspection(client, inspector_a.id)
    own_2 = create_assigned_inspection(client, inspector_a.id)
    other = create_assigned_inspection(client, inspector_b.id)

    admin_response = client.get("/api/v1/inspections")
    assert admin_response.status_code == 200
    assert {item["id"] for item in admin_response.json()} == {
        own_1["id"],
        own_2["id"],
        other["id"],
    }

    auth_as(inspector_a)
    response = client.get("/api/v1/inspections")
    assert response.status_code == 200
    assert {item["id"] for item in response.json()} == {own_1["id"], own_2["id"]}


def test_inspector_cannot_get_unassigned_inspection(client, db_session, auth_as):
    inspector_a = create_user_record(db_session, "inspector")
    inspector_b = create_user_record(db_session, "inspector")
    own = create_assigned_inspection(client, inspector_a.id)
    other = create_assigned_inspection(client, inspector_b.id)
    unassigned = create_assigned_inspection(client, None)

    auth_as(inspector_a)

    assert client.get(f"/api/v1/inspections/{own['id']}").status_code == 200

    for forbidden in (other, unassigned):
        response = client.get(f"/api/v1/inspections/{forbidden['id']}")
        assert response.status_code == 403
        assert response.json()["detail"] == INSPECTION_ACCESS_DENIED_DETAIL

    assert client.get("/api/v1/inspections/999999").status_code == 404


def test_status_transition_inspector_registers_actor_and_notes(
    client, db_session, auth_as
):
    inspector = create_user_record(db_session, "inspector")
    inspection = create_assigned_inspection(client, inspector.id)
    draft = create_report_draft_record(db_session, inspection["id"])
    notes = "Se completaron las evidencias fotográficas y se solicita revisión técnica."

    auth_as(inspector)
    response = client.post(
        status_transition_url(inspection["id"]),
        json={"to_status": "in_review", "notes": notes},
    )

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["inspection_id"] == inspection["id"]
    assert body["report_draft_id"] == draft.id
    assert body["from_status"] == "draft"
    assert body["status"] == "in_review"
    assert body["status_updated_by"] == inspector.id
    assert body["operational_status"] == "in_progress"

    db_session.expire_all()
    log = (
        db_session.query(ReportStatusLog)
        .filter(ReportStatusLog.report_draft_id == draft.id)
        .one()
    )
    assert log.from_status == "draft"
    assert log.to_status == "in_review"
    assert log.actor_user_id == inspector.id
    assert log.notes == notes
    assert log.created_at is not None

    assert client.get(f"/api/v1/inspections/{inspection['id']}").json()["status"] == "in_review"
    productivity = get_productivity_record(db_session, inspection["id"])
    assert productivity.operational_status == "in_progress"
    assert productivity.report_started_at is not None


def test_status_transition_inspector_moves_between_non_final_states(
    client, db_session, auth_as
):
    inspector = create_user_record(db_session, "inspector")
    inspection = create_assigned_inspection(client, inspector.id)
    draft = create_report_draft_record(db_session, inspection["id"])

    auth_as(inspector)
    for target, operational in (
        ("in_review", "in_progress"),
        ("observed", "blocked"),
        ("draft", "pending"),
    ):
        response = client.post(
            status_transition_url(inspection["id"]),
            json={"to_status": target},
        )
        assert response.status_code == 200, response.json()
        assert response.json()["status"] == target
        assert response.json()["operational_status"] == operational

    assert get_draft_status(db_session, draft.id) == "draft"


def test_status_transition_inspector_cannot_finalize(client, db_session, auth_as):
    inspector = create_user_record(db_session, "inspector")
    inspection = create_assigned_inspection(client, inspector.id)
    draft = create_report_draft_record(db_session, inspection["id"])

    auth_as(inspector)
    response = client.post(
        status_transition_url(inspection["id"]),
        json={"to_status": "finalized", "notes": "intento de cierre"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == FINALIZE_FORBIDDEN_DETAIL
    assert get_draft_status(db_session, draft.id) == "draft"
    assert db_session.query(ReportStatusLog).count() == 0


def test_status_transition_inspector_cannot_touch_unassigned_inspection(
    client, db_session, auth_as
):
    inspector_a = create_user_record(db_session, "inspector")
    inspector_b = create_user_record(db_session, "inspector")
    inspection = create_assigned_inspection(client, inspector_a.id)
    draft = create_report_draft_record(db_session, inspection["id"])

    auth_as(inspector_b)
    response = client.post(
        status_transition_url(inspection["id"]),
        json={"to_status": "in_review"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == INSPECTION_ACCESS_DENIED_DETAIL
    assert get_draft_status(db_session, draft.id) == "draft"


def test_status_transition_without_draft_returns_404(client):
    inspection = create_assigned_inspection(client, None)

    response = client.post(
        status_transition_url(inspection["id"]),
        json={"to_status": "in_review"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == REPORT_DRAFT_NOT_FOUND_DETAIL


def test_status_transition_admin_can_finalize_and_reopen(client, db_session):
    inspection = create_assigned_inspection(client, None)
    draft = create_report_draft_record(db_session, inspection["id"])
    url = status_transition_url(inspection["id"])

    finalize = client.post(url, json={"to_status": "finalized", "notes": "aprobado"})
    assert finalize.status_code == 200, finalize.json()
    assert finalize.json()["status"] == "finalized"
    assert finalize.json()["operational_status"] == "completed"
    assert get_productivity_record(db_session, inspection["id"]).report_finished_at is not None

    reopen = client.post(url, json={"to_status": "in_review", "notes": "reapertura"})
    assert reopen.status_code == 200, reopen.json()
    assert reopen.json()["from_status"] == "finalized"
    assert reopen.json()["status"] == "in_review"
    assert reopen.json()["operational_status"] == "in_progress"

    productivity = get_productivity_record(db_session, inspection["id"])
    assert productivity.report_finished_at is None
    assert productivity.duration_minutes is None
    assert productivity.met_goal is None

    db_session.expire_all()
    logs = (
        db_session.query(ReportStatusLog)
        .filter(ReportStatusLog.report_draft_id == draft.id)
        .order_by(ReportStatusLog.id.asc())
        .all()
    )
    assert [(log.from_status, log.to_status) for log in logs] == [
        ("draft", "finalized"),
        ("finalized", "in_review"),
    ]
    assert [log.notes for log in logs] == ["aprobado", "reapertura"]


def test_status_transition_inspector_cannot_reopen_finalized(
    client, db_session, auth_as
):
    inspector = create_user_record(db_session, "inspector")
    inspection = create_assigned_inspection(client, inspector.id)
    draft = create_report_draft_record(db_session, inspection["id"])
    url = status_transition_url(inspection["id"])

    assert client.post(url, json={"to_status": "finalized"}).status_code == 200

    auth_as(inspector)
    response = client.post(url, json={"to_status": "in_review"})

    assert response.status_code == 403
    assert response.json()["detail"] == REOPEN_FORBIDDEN_DETAIL
    assert get_draft_status(db_session, draft.id) == "finalized"


def test_legacy_patch_status_enforces_role_and_actor(client, db_session, auth_as):
    inspector = create_user_record(db_session, "inspector")
    inspection = create_assigned_inspection(client, inspector.id)
    draft = create_report_draft_record(db_session, inspection["id"])
    url = f"/api/v1/reports/{draft.id}/status"

    auth_as(inspector)

    forbidden = client.patch(url, json={"status": "finalized"})
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"] == FINALIZE_FORBIDDEN_DETAIL

    allowed = client.patch(url, json={"status": "in_review", "notes": "revisión"})
    assert allowed.status_code == 200, allowed.json()
    assert allowed.json()["status_updated_by"] == inspector.id

    db_session.expire_all()
    log = db_session.query(ReportStatusLog).filter(ReportStatusLog.report_draft_id == draft.id).one()
    assert log.actor_user_id == inspector.id
    assert log.notes == "revisión"


def test_legacy_patch_status_blocks_unassigned_inspector(client, db_session, auth_as):
    inspector_a = create_user_record(db_session, "inspector")
    inspector_b = create_user_record(db_session, "inspector")
    inspection = create_assigned_inspection(client, inspector_a.id)
    draft = create_report_draft_record(db_session, inspection["id"])

    auth_as(inspector_b)
    response = client.patch(
        f"/api/v1/reports/{draft.id}/status",
        json={"status": "in_review"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == INSPECTION_ACCESS_DENIED_DETAIL


def test_export_report_dual_auth_and_disposition(client, db_session, tmp_path, monkeypatch):
    inspection = create_inspection_via_api(client)
    draft = create_report_draft_record(db_session, inspection["id"])

    docx_path = tmp_path / "report.docx"
    docx_path.write_bytes(b"PK fake-docx")

    monkeypatch.setattr(report_export_routes, "export_report_docx", lambda db, draft_id: str(docx_path))

    # Con query param token o auth
    res = client.get(f"/api/v1/report-export/docx/{draft.id}?token=some_token")
    assert res.status_code == 200
    assert "attachment; filename=" in res.headers.get("content-disposition", "")


def test_report_status_routes_suite(client, db_session, auth_as):
    admin = create_user_record(db_session, "admin")
    inspector = create_user_record(db_session, "inspector")
    inspection = create_assigned_inspection(client, inspector.id)
    draft = create_report_draft_record(db_session, inspection["id"])

    auth_as(admin)

    # 1. available-transitions
    res_avail = client.get(f"/api/v1/report-status/{inspection['id']}/available-transitions")
    assert res_avail.status_code == 200
    data_avail = res_avail.json()
    assert data_avail["inspection_id"] == inspection["id"]
    assert "in_review" in data_avail["available_transitions"]

    # 2. transition
    res_trans = client.post(
        f"/api/v1/report-status/{inspection['id']}/transition",
        json={"new_status": "in_review", "comment": "Inicio de revisión técnica"},
    )
    assert res_trans.status_code == 200
    data_trans = res_trans.json()
    assert data_trans["status"] == "in_review"
    assert data_trans["log"]["comment"] == "Inicio de revisión técnica"
    assert data_trans["log"]["new_status"] == "in_review"

    # 3. history
    res_hist = client.get(f"/api/v1/report-status/{inspection['id']}/history")
    assert res_hist.status_code == 200
    logs = res_hist.json()
    assert len(logs) >= 1
    assert logs[0]["new_status"] == "in_review"

    # 4. overview
    res_over = client.get("/api/v1/report-status/overview")
    assert res_over.status_code == 200
    overview = res_over.json()
    matching = [item for item in overview if item["inspection_id"] == inspection["id"]]
    assert len(matching) == 1
    assert matching[0]["current_status"] == "in_review"
    assert matching[0]["total_transitions"] >= 1


def test_export_report_pdf_real_build_regression(client, db_session, tmp_path):
    from app.services.report_export_service import export_report_pdf

    inspection = create_inspection_via_api(client)
    draft = create_report_draft_record(db_session, inspection["id"])

    target_pdf = tmp_path / "real_output.pdf"
    result_path = export_report_pdf(db_session, draft.id, output_path=target_pdf)

    assert Path(result_path).exists()
    assert Path(result_path).stat().st_size > 0
    content = Path(result_path).read_bytes()
    assert content.startswith(b"%PDF")

