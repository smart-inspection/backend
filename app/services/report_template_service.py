import re
import unicodedata
from collections import defaultdict
from typing import Any

from sqlalchemy.orm import Session, selectinload

from app.db.models import Inspection, ReportDraft, Transcription


SECTION_MARKERS = [
    "1. RESUMEN EJECUTIVO",
    "2. CONTEXTO DE LA INSPECCIÓN",
    "3. HALLAZGOS PRINCIPALES",
    "4. VALIDACIÓN OCR",
    "5. OBSERVACIONES TRANSCRITAS",
    "6. RECOMENDACIONES",
    "7. INFORME REDACTADO",
    "1. DATOS GENERALES",
    "2. IDENTIFICACIÓN DE CAMPOS CRÍTICOS",
    "3. DATOS CAPTURADOS EN INSPECCIÓN",
    "4. EVIDENCIAS REGISTRADAS",
    "5. VALIDACIÓN OCR",
    "6. OBSERVACIONES TRANSCRITAS",
    "7. CONCLUSIÓN PRELIMINAR",
]

ISSUE_KEYWORDS = (
    "desgaste",
    "fisura",
    "grieta",
    "fractura",
    "deformacion",
    "deformación",
    "corrosion",
    "corrosión",
    "fuga",
    "daño",
    "dano",
    "rotura",
    "rechazado",
    "reparacion",
    "reparación",
    "soldadura",
    "golpe",
    "quebrado",
    "no conforme",
    "observado",
)


def _safe_text(value: Any, default: str = "No registrado") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _format_date(value: Any, default: str = "No registrada") -> str:
    if value is None:
        return default
    if hasattr(value, "strftime"):
        return value.strftime("%d/%m/%Y")
    text = str(value).strip()
    return text if text else default


def _normalize_key(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def _humanize_key(value: str | None) -> str:
    normalized = _normalize_key(value)
    if not normalized:
        return "Componente"
    return normalized.replace("_", " ").title()


def _pick_attr(obj: Any, candidates: list[str], default: str = "No registrado") -> str:
    for name in candidates:
        value = getattr(obj, name, None)
        if value is None:
            continue
        if hasattr(value, "strftime"):
            return _format_date(value, default)
        text = str(value).strip()
        if text:
            return text
    return default


def _field_best_value(field: Any, default: str = "No registrado") -> str:
    for attr in ("final_value", "manual_value", "ocr_value"):
        value = getattr(field, attr, None)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def _draft_text(draft: ReportDraft | None) -> str:
    if not draft:
        return ""
    return (draft.edited_text or draft.generated_text or "").strip()


def _extract_section(text: str, headings: list[str], fallback: str = "") -> str:
    if not text:
        return fallback

    upper_text = text.upper()
    matches: list[tuple[int, str]] = []

    for heading in headings:
        idx = upper_text.find(heading.upper())
        if idx != -1:
            matches.append((idx, heading))

    if not matches:
        return fallback

    start_idx, matched_heading = min(matches, key=lambda item: item[0])
    section_text = text[start_idx + len(matched_heading):].strip()

    upper_section = section_text.upper()
    end_positions = []
    for marker in SECTION_MARKERS:
        pos = upper_section.find(marker.upper())
        if pos != -1:
            end_positions.append(pos)

    if end_positions:
        section_text = section_text[: min(end_positions)].strip()

    return section_text or fallback


def _has_issue_text(value: str | None) -> bool:
    normalized = _normalize_key(value or "")
    if not normalized:
        return False
    normalized_text = normalized.replace("_", " ")
    return any(keyword in normalized_text for keyword in ISSUE_KEYWORDS)


def _get_field_map(inspection: Inspection) -> dict[str, str]:
    data: dict[str, str] = {}
    for field in getattr(inspection, "fields", []) or []:
        value = _field_best_value(field, default="")
        if not value:
            continue

        field_key = _normalize_key(getattr(field, "field_key", None))
        field_label = _normalize_key(getattr(field, "field_label", None))

        if field_key:
            data[field_key] = value
        if field_label:
            data[field_label] = value

    return data


def _find_field(field_map: dict[str, str], aliases: list[str], default: str = "No registrado") -> str:
    for alias in aliases:
        key = _normalize_key(alias)
        value = field_map.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def _build_intro_paragraph(
    inspection: Inspection,
    methods: list[str],
    evidence_count: int,
    transcription_count: int,
) -> str:
    requested_by = _safe_text(inspection.requested_by, inspection.client_name)
    equipment_type = _safe_text(inspection.equipment_type)
    code = _safe_text(inspection.code)
    inspection_type = _safe_text(inspection.inspection_type)
    inspection_date = _format_date(inspection.inspection_date)
    location = _safe_text(inspection.location, "ubicación no registrada")

    return (
        f"Por solicitud de {requested_by}, se realizó la inspección {inspection_type.lower()} del equipo "
        f"{equipment_type} identificado con código {code}, con fecha {inspection_date} en {location}. "
        f"El informe consolida datos estructurados, {evidence_count} evidencia(s) registrada(s), "
        f"{transcription_count} transcripción(es) y los métodos aplicados: {', '.join(methods)}."
    )


def _build_objective(
    inspection: Inspection,
    extracted_summary: str,
) -> str:
    if extracted_summary:
        return extracted_summary

    return (
        f"Determinar el estado documentado del equipo {inspection.equipment_type} mediante la revisión "
        f"de datos estructurados, validación OCR, evidencias registradas y observaciones del inspector, "
        f"con la finalidad de emitir un informe técnico uniforme y verificable."
    )


def _build_scope(inspection: Inspection, evidences: list[Any], transcriptions: list[Any]) -> list[str]:
    items = [
        f"Revisión de los datos capturados para la inspección {inspection.code}.",
        "Verificación de campos críticos y consistencia entre valor manual, OCR y valor final.",
        "Organización del informe bajo una plantilla estructurada para exportación documental.",
    ]

    if evidences:
        items.append("Incorporación de evidencias fotográficas o documentales asociadas a la inspección.")
    if transcriptions:
        items.append("Incorporación de observaciones transcritas vinculadas al trabajo de campo.")

    return items


def _build_protocol(inspection: Inspection, evidences: list[Any], transcriptions: list[Any]) -> str:
    parts = [
        f"La inspección fue registrada bajo el tipo '{inspection.inspection_type}'.",
        "La información fue consolidada a partir del formulario estructurado de inspección.",
    ]
    if evidences:
        parts.append("Se consideraron evidencias asociadas al registro para sustento documental.")
    if transcriptions:
        parts.append("Se consideraron observaciones obtenidas desde transcripción de audio.")
    return " ".join(parts)


def _build_standards() -> list[str]:
    return [
        "Plantilla estandarizada de inspección técnica del sistema.",
        "Validación cruzada entre captura manual, OCR y revisión final.",
        "Criterios internos de consistencia documental y trazabilidad del informe.",
    ]


def _build_methods(evidences: list[Any], transcriptions: list[Any]) -> list[str]:
    methods = ["INSPECCIÓN VISUAL (VT)"]

    has_ocr = any(
        bool(getattr(item, "ocr_processed", False) or getattr(item, "ocr_extracted_text", None))
        for item in evidences or []
    )
    has_images = any(
        "image" in _safe_text(getattr(item, "file_type", None), "").lower()
        or _safe_text(getattr(item, "file_type", None), "").lower() in {"jpg", "jpeg", "png", "webp"}
        for item in evidences or []
    )
    has_transcriptions = any(
        bool((getattr(item, "final_text", None) or getattr(item, "raw_text", None) or "").strip())
        for item in transcriptions or []
    )

    if has_images:
        methods.append("REGISTRO FOTOGRÁFICO")
    if has_ocr:
        methods.append("VALIDACIÓN DOCUMENTAL (OCR)")
    if has_transcriptions:
        methods.append("TRANSCRIPCIÓN DE OBSERVACIONES")

    return methods


def _build_inspection_equipment(evidences: list[Any], transcriptions: list[Any]) -> dict[str, list[str]]:
    mt_items = [
        "Formulario digital de inspección",
        "Motor de validación de campos críticos",
    ]
    vt_items = [
        "Cámara o dispositivo de captura",
        "Registro fotográfico digital",
        "Revisión visual del inspector",
    ]

    if any(bool(getattr(item, "ocr_processed", False)) for item in evidences or []):
        mt_items.append("Módulo OCR para lectura documental")

    if transcriptions:
        vt_items.append("Módulo de transcripción de audio")

    return {"mt": mt_items, "vt": vt_items}


def _build_criteria() -> dict[str, str]:
    return {
        "accepted": "Registro completo, consistente y sin discrepancias relevantes en los campos críticos o evidencias revisadas.",
        "rejected": "Registro con inconsistencias documentales, observaciones críticas o evidencia insuficiente para validación.",
        "retirement": "La emisión final del informe debe quedar supeditada a la validación técnica y documental del responsable.",
    }


def _build_findings_from_fields(fields: list[Any]) -> str:
    if not fields:
        return "No se registraron hallazgos específicos."

    issue_lines: list[str] = []
    info_lines: list[str] = []

    for field in fields:
        label = _safe_text(getattr(field, "field_label", None), _safe_text(getattr(field, "field_key", None), "Campo"))
        value = _field_best_value(field, default="")
        if not value:
            continue

        line = f"- {label}: {value}"
        status = _safe_text(getattr(field, "validation_status", None), "pending").lower()
        message = _safe_text(getattr(field, "validation_message", None), "")

        if _has_issue_text(value) or status in {"mismatch", "not_found"}:
            if message:
                line = f"{line} ({message})"
            issue_lines.append(line)
        else:
            info_lines.append(line)

    selected = issue_lines if issue_lines else info_lines[:8]
    return "\n".join(selected) if selected else "No se registraron hallazgos específicos."


def _build_ocr_summary_from_fields(fields: list[Any]) -> str:
    if not fields:
        return "No hay resultados OCR asociados."

    matched = 0
    mismatched = 0
    not_found = 0
    pending = 0
    details: list[str] = []

    for field in fields:
        status = _safe_text(getattr(field, "validation_status", None), "pending").lower()
        label = _safe_text(getattr(field, "field_label", None), _safe_text(getattr(field, "field_key", None), "Campo"))
        manual_value = _safe_text(getattr(field, "manual_value", None))
        ocr_value = _safe_text(getattr(field, "ocr_value", None))
        message = _safe_text(getattr(field, "validation_message", None), "")

        if status == "matched":
            matched += 1
        elif status == "mismatch":
            mismatched += 1
        elif status == "not_found":
            not_found += 1
        else:
            pending += 1

        if status in {"mismatch", "not_found"}:
            detail = f"- {label}: manual='{manual_value}' | ocr='{ocr_value}' | estado='{status}'"
            if message:
                detail += f" | detalle='{message}'"
            details.append(detail)

    lines = [
        f"Coincidencias: {matched}.",
        f"Discrepancias: {mismatched}.",
        f"No detectados: {not_found}.",
        f"Pendientes: {pending}.",
    ]

    if details:
        lines.append("")
        lines.append("Campos con observación:")
        lines.extend(details[:10])
    else:
        lines.append("")
        lines.append("No se registraron discrepancias OCR relevantes.")

    return "\n".join(lines).strip()


def _build_voice_summary_from_transcriptions(transcriptions: list[Transcription]) -> str:
    if not transcriptions:
        return "No se registraron transcripciones asociadas."

    blocks: list[str] = []
    for idx, item in enumerate(transcriptions, start=1):
        text = (item.final_text or item.raw_text or "").strip()
        if not text:
            continue

        confidence = getattr(item, "confidence", None)
        confidence_text = ""
        if confidence is not None:
            confidence_text = f" | confianza={confidence}"

        blocks.append(
            "\n".join(
                [
                    f"Transcripción {idx} | idioma={_safe_text(item.language, 'No registrado')} | modelo={_safe_text(item.model_name, 'No registrado')}{confidence_text}",
                    text,
                ]
            )
        )

    return "\n\n".join(blocks) if blocks else "No se registraron transcripciones asociadas."


def _build_recommendations_from_fields(
    fields: list[Any],
    evidences: list[Any],
    transcriptions: list[Any],
) -> str:
    mismatches = sum(
        1 for field in fields or []
        if _safe_text(getattr(field, "validation_status", None), "pending").lower() == "mismatch"
    )
    issue_values = sum(
        1 for field in fields or []
        if _has_issue_text(_field_best_value(field, default=""))
    )

    recommendations: list[str] = []

    if issue_values > 0:
        recommendations.append("Realizar revisión técnica específica de los componentes con observaciones registradas.")
    if mismatches > 0:
        recommendations.append("Validar manualmente placa, VIN, series y demás campos con discrepancias OCR antes de aprobar el informe.")
    if not evidences:
        recommendations.append("Adjuntar evidencias fotográficas o documentales que respalden el informe final.")
    if not transcriptions:
        recommendations.append("Registrar observaciones complementarias del inspector para enriquecer el sustento técnico.")
    if not recommendations:
        recommendations.append("Completar la revisión técnica final y emitir el informe definitivo si no existen observaciones pendientes.")

    return "\n".join(f"- {item}" for item in recommendations)


def _build_conclusion_from_state(
    inspection: Inspection,
    fields: list[Any],
    evidences: list[Any],
    transcriptions: list[Any],
) -> str:
    mismatch_count = sum(
        1 for field in fields or []
        if _safe_text(getattr(field, "validation_status", None), "pending").lower() == "mismatch"
    )
    issue_count = sum(
        1 for field in fields or []
        if _has_issue_text(_field_best_value(field, default=""))
    )
    evidence_count = len(evidences or [])
    transcription_count = len([item for item in transcriptions or [] if (item.final_text or item.raw_text or "").strip()])

    if issue_count > 0:
        return (
            f"El informe de la inspección {inspection.code} consolida información estructurada, "
            f"{evidence_count} evidencia(s) y {transcription_count} transcripción(es). "
            "Se identificaron observaciones técnicas registradas en los campos del informe, por lo que "
            "se recomienda validación final del responsable antes de su emisión definitiva."
        )

    if mismatch_count > 0:
        return (
            f"El informe de la inspección {inspection.code} fue construido con datos estructurados y sustento documental, "
            "pero presenta discrepancias OCR en campos críticos, por lo que requiere revisión humana antes de su aprobación."
        )

    return (
        f"El informe de la inspección {inspection.code} fue construido con la información disponible en el sistema, "
        f"incluyendo {evidence_count} evidencia(s) y {transcription_count} transcripción(es). "
        "No se identificaron discrepancias críticas en los campos comparados, quedando sujeto a validación técnica final."
    )


def _derive_group_condition(group_fields: list[Any]) -> str:
    explicit_condition_aliases = {
        "aceptado": "Aceptado",
        "aprobado": "Aceptado",
        "conforme": "Aceptado",
        "ok": "Aceptado",
        "rechazado": "Rechazado",
        "observado": "Observado",
        "pendiente": "Pendiente",
    }

    for field in group_fields:
        key = _normalize_key(getattr(field, "field_key", None))
        if "condicion" in key or "estado" in key or "resultado" in key:
            value = _field_best_value(field, default="")
            normalized = _normalize_key(value).replace("_", " ")
            for alias, mapped in explicit_condition_aliases.items():
                if alias in normalized:
                    return mapped

    issue_detected = any(_has_issue_text(_field_best_value(field, default="")) for field in group_fields)
    mismatch_detected = any(
        _safe_text(getattr(field, "validation_status", None), "pending").lower() == "mismatch"
        for field in group_fields
    )
    pending_detected = any(
        _safe_text(getattr(field, "validation_status", None), "pending").lower() in {"pending", "not_found", "not_evaluated"}
        for field in group_fields
    )

    if issue_detected:
        return "Observado"
    if mismatch_detected:
        return "Observado"
    if pending_detected:
        return "Pendiente"
    return "Registrado"


def _derive_group_action(condition: str) -> str:
    normalized = _normalize_key(condition)
    if normalized in {"observado", "rechazado"}:
        return "Revisar y definir acción correctiva"
    if normalized == "pendiente":
        return "Completar revisión técnica"
    if normalized == "aceptado":
        return "--"
    return "Validar en revisión final"


def _truncate(value: str, max_len: int = 140) -> str:
    text = _safe_text(value, "")
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."


def _build_group_observation(group_fields: list[Any]) -> str:
    issue_lines: list[str] = []
    normal_lines: list[str] = []

    for field in group_fields:
        label = _safe_text(getattr(field, "field_label", None), _safe_text(getattr(field, "field_key", None), "Campo"))
        value = _field_best_value(field, default="")
        if not value:
            continue

        line = f"{label}: {_truncate(value, 90)}"
        if _has_issue_text(value):
            issue_lines.append(line)
        else:
            normal_lines.append(line)

    selected = issue_lines[:2] if issue_lines else normal_lines[:2]
    return " | ".join(selected) if selected else "Sin observaciones detalladas."


def _build_results_rows(inspection: Inspection, fields: list[Any]) -> list[dict[str, str]]:
    groups: dict[str, list[Any]] = defaultdict(list)
    ignored_groups = {
        "general",
        "datos_generales",
        "identificacion",
        "identificacion_general",
        "ocr",
        "transcripcion",
        "metadata",
        "cabecera",
    }

    for field in fields or []:
        group = _normalize_key(getattr(field, "field_group", None))
        if not group or group in ignored_groups:
            continue
        groups[group].append(field)

    rows: list[dict[str, str]] = []

    if groups:
        for group_name, group_fields in groups.items():
            condition = _derive_group_condition(group_fields)
            rows.append(
                {
                    "equipo": inspection.equipment_type,
                    "componente": _humanize_key(group_name),
                    "condicion": condition,
                    "observaciones": _build_group_observation(group_fields),
                    "accion": _derive_group_action(condition),
                }
            )

    if not rows:
        fallback_condition = _derive_group_condition(fields or [])
        rows.append(
            {
                "equipo": inspection.equipment_type,
                "componente": "Estructura general",
                "condicion": fallback_condition,
                "observaciones": _build_group_observation(fields or []),
                "accion": _derive_group_action(fallback_condition),
            }
        )

    return rows[:12]


def _build_evidences(
    inspection: Inspection,
    transcriptions: list[Transcription],
) -> list[dict[str, Any]]:
    evidence_transcription_map: dict[int, list[str]] = defaultdict(list)
    for item in transcriptions or []:
        if getattr(item, "evidence_id", None) is None:
            continue
        text = (item.final_text or item.raw_text or "").strip()
        if text:
            evidence_transcription_map[item.evidence_id].append(text)

    evidences: list[dict[str, Any]] = []
    for idx, evidence in enumerate(getattr(inspection, "evidences", []) or [], start=1):
        linked_transcriptions = evidence_transcription_map.get(evidence.id, [])
        ocr_text = _safe_text(getattr(evidence, "ocr_extracted_text", None), "")
        if linked_transcriptions:
            transcribed_block = " | ".join(linked_transcriptions[:2])
            ocr_text = f"{ocr_text}\n{transcribed_block}".strip() if ocr_text else transcribed_block

        evidences.append(
            {
                "index": idx,
                "path": getattr(evidence, "file_path", None),
                "category": _safe_text(getattr(evidence, "evidence_category", None), "Evidencia general"),
                "caption": _safe_text(getattr(evidence, "caption", None), f"Foto {idx}"),
                "ocr_text": ocr_text,
                "file_type": _safe_text(getattr(evidence, "file_type", None), "No registrado"),
                "ocr_processed": bool(getattr(evidence, "ocr_processed", False)),
            }
        )

    if not evidences:
        evidences = [
            {
                "index": 1,
                "path": None,
                "category": "Evidencia pendiente",
                "caption": "Espacio reservado para evidencia fotográfica",
                "ocr_text": "",
                "file_type": "No registrado",
                "ocr_processed": False,
            }
        ]

    return evidences


def _infer_general_condition(field_map: dict[str, str], fields: list[Any]) -> str:
    explicit = _find_field(
        field_map,
        [
            "condicion_general",
            "estado_general",
            "resultado_inspeccion",
            "resultado_final",
            "general_condition",
            "overall_condition",
        ],
        default="",
    )
    if explicit:
        return explicit.upper()

    issue_count = sum(1 for field in fields or [] if _has_issue_text(_field_best_value(field, default="")))
    mismatch_count = sum(
        1 for field in fields or []
        if _safe_text(getattr(field, "validation_status", None), "pending").lower() == "mismatch"
    )

    if issue_count > 0:
        return "OBSERVADO"
    if mismatch_count > 0:
        return "PENDIENTE DE VALIDACIÓN"
    if fields:
        return "REGISTRADO"
    return "PENDIENTE"


def build_company_report_context(db: Session, draft_id: int) -> dict[str, Any]:
    draft = db.query(ReportDraft).filter(ReportDraft.id == draft_id).first()
    if not draft:
        raise ValueError("Report draft not found")

    inspection = (
        db.query(Inspection)
        .options(
            selectinload(Inspection.fields),
            selectinload(Inspection.evidences),
        )
        .filter(Inspection.id == draft.inspection_id)
        .first()
    )
    if not inspection:
        raise ValueError("Inspection not found")

    transcriptions = (
        db.query(Transcription)
        .filter(Transcription.inspection_id == inspection.id)
        .order_by(Transcription.id.asc())
        .all()
    )

    fields = list(getattr(inspection, "fields", []) or [])
    evidences_raw = list(getattr(inspection, "evidences", []) or [])
    field_map = _get_field_map(inspection)
    full_text = _draft_text(draft)

    extracted_summary = _extract_section(full_text, ["1. RESUMEN EJECUTIVO"], "")
    extracted_context = _extract_section(
        full_text,
        ["2. CONTEXTO DE LA INSPECCIÓN", "1. DATOS GENERALES"],
        "",
    )
    extracted_findings = _extract_section(
        full_text,
        ["3. HALLAZGOS PRINCIPALES", "2. IDENTIFICACIÓN DE CAMPOS CRÍTICOS", "3. DATOS CAPTURADOS EN INSPECCIÓN"],
        "",
    )
    extracted_ocr = _extract_section(full_text, ["4. VALIDACIÓN OCR", "5. VALIDACIÓN OCR"], "")
    extracted_voice = _extract_section(full_text, ["5. OBSERVACIONES TRANSCRITAS", "6. OBSERVACIONES TRANSCRITAS"], "")
    extracted_recommendations = _extract_section(full_text, ["6. RECOMENDACIONES"], "")
    extracted_conclusion = _extract_section(
        full_text,
        ["7. INFORME REDACTADO", "7. CONCLUSIÓN PRELIMINAR"],
        "",
    )

    plate = _find_field(field_map, ["placa", "plate", "license_plate", "numero_placa"])
    vin = _find_field(field_map, ["vin", "n_vin", "numero_vin", "no_vin"])
    brand = _find_field(field_map, ["marca", "brand"])
    year = _find_field(field_map, ["anio_fabricacion", "año_fabricacion", "year", "manufacture_year"])
    mileage = _find_field(field_map, ["kilometraje", "mileage", "odometro", "odómetro"])
    age = _find_field(field_map, ["antiguedad", "antigüedad", "age"])
    axles = _find_field(field_map, ["numero_ejes", "n_ejes", "ejes", "axles"])
    payload = _find_field(field_map, ["carga_util", "payload", "carga"])
    net_weight = _find_field(field_map, ["peso_neto", "net_weight", "tara"])
    king_pin_brand = _find_field(field_map, ["marca_king_pin", "king_pin_brand"])
    king_pin_model = _find_field(field_map, ["modelo_king_pin", "king_pin_model"])
    king_pin_serial = _find_field(field_map, ["serie_king_pin", "serial_king_pin", "king_pin_serial"])

    methods = _build_methods(evidences_raw, transcriptions)
    evidences = _build_evidences(inspection, transcriptions)
    findings = extracted_findings or _build_findings_from_fields(fields)
    ocr_summary = extracted_ocr or _build_ocr_summary_from_fields(fields)
    voice_summary = extracted_voice or _build_voice_summary_from_transcriptions(transcriptions)
    recommendations = extracted_recommendations or _build_recommendations_from_fields(fields, evidences_raw, transcriptions)
    conclusion = extracted_conclusion or _build_conclusion_from_state(inspection, fields, evidences_raw, transcriptions)

    requested_by = _safe_text(inspection.requested_by, inspection.client_name)
    location = _safe_text(inspection.location, "No registrada")
    intro_paragraph = extracted_context or _build_intro_paragraph(
        inspection=inspection,
        methods=methods,
        evidence_count=len(evidences_raw),
        transcription_count=len(transcriptions),
    )

    context = {
        "draft": draft,
        "inspection": inspection,
        "header": {
            "report_title": "INFORME FINAL",
            "report_code": inspection.code,
            "equipment_display": f"{inspection.equipment_type}: {plate}" if plate != "No registrado" else inspection.equipment_type,
            "inspection_type": _safe_text(inspection.inspection_type, "No registrado").upper(),
            "inspection_date": _format_date(inspection.inspection_date),
            "methods": methods,
            "general_condition": _infer_general_condition(field_map, fields),
            "location": location.upper(),
        },
        "technical_info": {
            "requested_by": requested_by,
            "address": _find_field(field_map, ["direccion", "address", "direccion_cliente"], location),
            "service_responsible": _safe_text(inspection.responsible_inspector, "Inspector no registrado"),
            "inspection_date_text": _format_date(inspection.inspection_date),
            "intro_paragraph": intro_paragraph,
        },
        "identification": {
            "tipo_equipo": _safe_text(inspection.equipment_type),
            "placa": plate,
            "marca": brand,
            "vin": vin,
            "anio_fabricacion": year,
            "kilometraje": mileage,
            "antiguedad": age,
            "numero_ejes": axles,
            "carga_util": payload,
            "peso_neto": net_weight,
            "marca_king_pin": king_pin_brand,
            "modelo_king_pin": king_pin_model,
            "serie_king_pin": king_pin_serial,
        },
        "objective": _build_objective(inspection, extracted_summary),
        "scope": _build_scope(inspection, evidences_raw, transcriptions),
        "protocol": _build_protocol(inspection, evidences_raw, transcriptions),
        "frequency": "La frecuencia de inspección deberá definirse según el tipo de servicio, condición operativa del equipo y política interna de control.",
        "standards": _build_standards(),
        "inspection_equipment": _build_inspection_equipment(evidences_raw, transcriptions),
        "criteria": _build_criteria(),
        "results": _build_results_rows(inspection, fields),
        "conclusion": conclusion,
        "ocr_summary": ocr_summary,
        "voice_summary": voice_summary,
        "recommendations": recommendations,
        "evidences": evidences,
        "findings": findings,
    }

    return context