import re
import unicodedata

from sqlalchemy.orm import Session, selectinload

from app.db.models import Inspection, InspectionField

CANONICAL_FIELD_SPECS = {
    "placa": ("Placa", "identificacion", "string"),
    "marca": ("Marca", "identificacion", "string"),
    "aniofabricacion": ("Año de fabricación", "identificacion", "number"),
    "numeroejes": ("N° de ejes", "identificacion", "number"),
    "cargautil": ("Carga útil", "identificacion", "number"),
    "pesoneto": ("Peso neto", "identificacion", "number"),
    "marcakingpin": ("Marca de King Pin", "identificacion", "string"),
    "modelokingpin": ("Modelo de King Pin", "identificacion", "string"),
    "seriekingpin": ("N° de serie de King Pin", "identificacion", "string"),
}

def normalize_key(value: str | None) -> str:
    if not value:
        return ""

    text = unicodedata.normalize("NFKD", value)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "", text)
    return text

def pick_best_value(field: InspectionField) -> str | None:
    for attr in ("final_value", "manual_value", "ocr_value"):
        value = getattr(field, attr, None)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None

def get_or_create_field(
    db: Session,
    inspection_id: int,
    field_key: str,
    field_label: str,
    field_group: str,
    expected_type: str,
) -> InspectionField:
    existing = (
        db.query(InspectionField)
        .filter(
            InspectionField.inspection_id == inspection_id,
            InspectionField.field_key == field_key,
        )
        .first()
    )
    if existing:
        return existing

    field = InspectionField(
        inspection_id=inspection_id,
        field_key=field_key,
        field_label=field_label,
        field_group=field_group,
        expected_type=expected_type,
        manual_value=None,
        ocr_value=None,
        final_value=None,
        validation_status="pending",
        validation_message=None,
        confidence=None,
    )
    db.add(field)
    db.flush()
    return field

def extract_plate_technical_data(text: str) -> dict[str, str]:
    if not text:
        return {}

    source = text.upper()
    result: dict[str, str] = {}

    patterns = {
        "placa": [
            r"PLACA[:\s]+([A-Z0-9\-]{5,12})",
        ],
        "marca": [
            r"MARCA[:\s]+([A-Z0-9\-/ ]{2,40})",
        ],
        "aniofabricacion": [
            r"A[ÑN]O(?:\s+DE\s+FABRICACI[ÓO]N)?[:\s]+(20\d{2}|19\d{2})",
        ],
        "numeroejes": [
            r"N[°º]?\s*(?:DE\s*)?EJES[:\s]+(\d+)",
            r"EJES[:\s]+(\d+)",
        ],
        "pesoneto": [
            r"PESO\s+NETO[:\s]+([0-9\.,]+)",
            r"TARA[:\s]+([0-9\.,]+)",
        ],
        "cargautil": [
            r"CARGA\s+[ÚU]TIL[:\s]+([0-9\.,]+)",
        ],
        "marcakingpin": [
            r"MARCA\s+KING\s*PIN[:\s]+([A-Z0-9\-/ ]{2,40})",
        ],
        "modelokingpin": [
            r"MODELO\s+KING\s*PIN[:\s]+([A-Z0-9\-/ ]{2,40})",
            r"MODELO[:\s]+([A-Z0-9\-/ ]{2,40})",
        ],
        "seriekingpin": [
            r"(?:SERIE|N[°º]?\s*DE\s*SERIE)\s+KING\s*PIN[:\s]+([A-Z0-9\-]+)",
            r"(?:N[°º]?\s*DE\s*SERIE|SERIE)[:\s]+([A-Z0-9\-]+)",
        ],
    }

    for field_key, regex_list in patterns.items():
        for regex in regex_list:
            match = re.search(regex, source)
            if match:
                result[field_key] = match.group(1).strip()
                break

    return result

def enrich_inspection_from_plate_technical(db: Session, inspection_id: int) -> dict:
    inspection = (
        db.query(Inspection)
        .options(
            selectinload(Inspection.fields),
            selectinload(Inspection.evidences),
        )
        .filter(Inspection.id == inspection_id)
        .first()
    )
    if not inspection:
        raise ValueError("Inspection not found")

    technical_plate_evidence = None
    for evidence in inspection.evidences or []:
        if getattr(evidence, "evidence_slot", None) == "plate_technical":
            technical_plate_evidence = evidence
            break

    if not technical_plate_evidence:
        return {
            "inspection_id": inspection_id,
            "evidence_id": None,
            "updated_fields": [],
            "message": "No existe evidencia con slot plate_technical",
        }

    ocr_text = getattr(technical_plate_evidence, "ocr_extracted_text", None) or ""
    extracted_data = extract_plate_technical_data(ocr_text)

    updated_fields = []

    for field_key, value in extracted_data.items():
        spec = CANONICAL_FIELD_SPECS.get(field_key)
        if not spec or not value:
            continue

        field_label, field_group, expected_type = spec

        field = get_or_create_field(
            db=db,
            inspection_id=inspection_id,
            field_key=field_key,
            field_label=field_label,
            field_group=field_group,
            expected_type=expected_type,
        )

        field.ocr_value = value

        if not (field.final_value and str(field.final_value).strip()):
            field.final_value = value

        updated_fields.append(
            {
                "field_key": field.field_key,
                "field_label": field.field_label,
                "ocr_value": field.ocr_value,
                "final_value": field.final_value,
            }
        )

    db.commit()

    return {
        "inspection_id": inspection_id,
        "evidence_id": technical_plate_evidence.id,
        "updated_fields": updated_fields,
        "message": "Enriquecimiento ejecutado",
    }