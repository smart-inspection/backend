import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import json

base_dir = Path(__file__).resolve().parents[3]

if str(base_dir) not in sys.path:
    sys.path.insert(0, str(base_dir))

from app.api.routes.evidences import get_db as evidences_get_db
from app.api.routes.inspection_enrichment import get_db as inspectionenrichment_get_db
from app.api.routes.inspection_fields import get_db as inspectionfields_get_db
from app.api.routes.inspection_requests import get_db as inspectionrequests_get_db
from app.api.routes.inspections import get_db as inspections_get_db
from app.api.routes.llm_report import get_db as llmreport_get_db
from app.api.routes.ocr import get_db as ocr_get_db
from app.api.routes.productivity import get_db as productivity_get_db
from app.api.routes.report_draft import get_db as reportdraft_get_db
from app.api.routes.report_export import get_db as reportexport_get_db
from app.api.routes.report_status import get_db as reportstatus_get_db
from app.api.routes.transcription import get_db as transcription_get_db
from app.db.base import Base
from app.main import app


sqlalchemy_database_url = "sqlite://"

engine = create_engine(
    sqlalchemy_database_url,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

db_session_factory = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def override_get_db():
    db = db_session_factory()

    try:
        yield db
    finally:
        db.close()

def log_api_response(
    method: str,
    endpoint: str,
    response,
) -> None:
    try:
        response_body = response.json()
        formatted_body = json.dumps(
            response_body,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    except ValueError:
        formatted_body = response.text or "<respuesta sin contenido>"

    print(
        f"\n{'=' * 80}\n"
        f"{method} {endpoint}\n"
        f"status_code: {response.status_code}\n"
        f"response:\n{formatted_body}\n"
        f"{'=' * 80}"
    )


@pytest.fixture(scope="function")
def client(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    (tmp_path / "uploads").mkdir(exist_ok=True)
    (tmp_path / "exports").mkdir(exist_ok=True)

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    app.dependency_overrides[inspections_get_db] = override_get_db
    app.dependency_overrides[inspectionfields_get_db] = override_get_db
    app.dependency_overrides[evidences_get_db] = override_get_db
    app.dependency_overrides[ocr_get_db] = override_get_db
    app.dependency_overrides[transcription_get_db] = override_get_db
    app.dependency_overrides[reportdraft_get_db] = override_get_db
    app.dependency_overrides[llmreport_get_db] = override_get_db
    app.dependency_overrides[reportexport_get_db] = override_get_db
    app.dependency_overrides[reportstatus_get_db] = override_get_db
    app.dependency_overrides[inspectionenrichment_get_db] = override_get_db
    app.dependency_overrides[productivity_get_db] = override_get_db
    app.dependency_overrides[inspectionrequests_get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)