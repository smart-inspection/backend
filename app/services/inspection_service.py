from datetime import datetime, timezone

from sqlalchemy.orm import Session, selectinload

from app.db.models import Inspection, InspectionProductivity, User
from app.db.models.evidence import Evidence
from app.db.models.transcription import Transcription
from app.schemas.inspection import InspectionCreate
from app.services.storage_service import delete_physical_file

VALID_INSPECTION_STATUSES = {"draft", "in_review", "observed", "finalized"}


def _resolve_inspector_name(user: User | None) -> str | None:
    if not user or not user.full_name:
        return None

    full_name = user.full_name.strip()
    return full_name or None


def update_inspection_status(db: Session, inspection_id: int, new_status: str) -> Inspection | None:
    inspection = get_inspection_by_id(db, inspection_id)
    if not inspection:
        return None

    normalized_status = (new_status or "").strip().lower()
    if normalized_status not in VALID_INSPECTION_STATUSES:
        raise ValueError(f"Invalid inspection status: {normalized_status}")

    inspection.status = normalized_status
    inspection.updated_at = datetime.now(timezone.utc)

    db.add(inspection)
    try:
        db.commit()
        db.refresh(inspection)
    except Exception:
        db.rollback()
        raise
    return inspection


def create_inspection(db: Session, payload: InspectionCreate) -> Inspection:
    responsible_user = None
    if payload.responsible_inspector_id is not None:
        responsible_user = (
            db.query(User)
            .filter(User.id == payload.responsible_inspector_id)
            .first()
        )
        if not responsible_user:
            raise ValueError("Responsible inspector not found")

    inspection = Inspection(**payload.model_dump())
    db.add(inspection)
    db.flush()

    productivity = InspectionProductivity(
        inspection_id=inspection.id,
        inspector_name=_resolve_inspector_name(responsible_user),
        scheduled_date=inspection.inspection_date,
        operational_status="pending",
    )
    db.add(productivity)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    created = get_inspection_by_id(db, inspection.id)
    if created:
        return created

    db.refresh(inspection)
    return inspection


def list_inspections(db: Session) -> list[Inspection]:
    return (
        db.query(Inspection)
        .options(selectinload(Inspection.responsible_inspector))
        .order_by(Inspection.id.desc())
        .all()
    )


def get_inspection_by_id(db: Session, inspection_id: int) -> Inspection | None:
    return (
        db.query(Inspection)
        .options(selectinload(Inspection.responsible_inspector))
        .filter(Inspection.id == inspection_id)
        .first()
    )


def eliminar_inspection(db: Session, inspection_id: int) -> bool:
    """
    Elimina una inspección con cascada completa:
    1. Borra físicamente archivos de evidencias.
    2. Borra físicamente archivos de audio de transcripciones.
    3. Elimina transcripciones explícitamente (sin cascade en modelo).
    4. db.delete(inspection) — ORM elimina en cascada: fields, evidences,
       productivity, report_drafts -> status_logs.
    Retorna True si fue eliminada, False si no existía.
    """
    inspection = (
        db.query(Inspection)
        .options(
            selectinload(Inspection.evidences),
            selectinload(Inspection.fields),
            selectinload(Inspection.report_drafts),
        )
        .filter(Inspection.id == inspection_id)
        .first()
    )
    if not inspection:
        return False

    # 1. Recolectar rutas físicas de evidencias
    rutas_evidencias = [e.file_path for e in inspection.evidences if e.file_path]

    # 2. Recolectar rutas físicas de transcripciones y eliminar registros
    transcripciones = (
        db.query(Transcription)
        .filter(Transcription.inspection_id == inspection_id)
        .all()
    )
    rutas_transcripciones = [
        t.source_file_path for t in transcripciones if t.source_file_path
    ]
    for transcripcion in transcripciones:
        db.delete(transcripcion)

    # 3. Eliminar inspección (cascada ORM: fields, evidences, productivity,
    #    report_drafts -> status_logs)
    db.delete(inspection)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    # 4. Borrar archivos físicos post-commit (fallo no revierte la BD)
    for ruta in rutas_evidencias:
        delete_physical_file(ruta)
    for ruta in rutas_transcripciones:
        delete_physical_file(ruta)

    return True