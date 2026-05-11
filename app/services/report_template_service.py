import re
import unicodedata
from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session, selectinload

from app.db.models import Inspection, ReportDraft, Transcription

COMPANY_LOGO_PATH = "app/static/reports/global_supplier_logo.png"

COMPANY_INFO = {
    "name": "GLOBAL SUPPLIER S&P SAC.",
    "ruc": "20477372571",
    "address": "Av. José María Eguren Sur 266 Int. 2 Urb. Palermo - Trujillo-Perú.",
    "phones": "Tel: 044-652077 cel. 923281042 - 965382425",
    "email": "ventas@globalsuppliersp.com",
    "website": "www.globalsuppliersp.com",
    "logo_path": COMPANY_LOGO_PATH,
}

SECTION_MARKERS = [
    "1. IDENTIFICACIÓN DEL EQUIPO INSPECCIONADO",
    "2. OBJETIVO",
    "3. ALCANCE",
    "4. PROTOCOLO EMPLEADO",
    "5. FRECUENCIA DE INSPECCIÓN",
    "6. NORMAS Y CODIGOS DE REFERENCIA",
    "6. NORMAS Y CÓDIGOS DE REFERENCIA",
    "7. EQUIPOS DE INSPECCIÓN EMPELADOS",
    "7. EQUIPOS DE INSPECCIÓN EMPLEADOS",
    "8. CRITERIOS DE INSPECCIÓN",
    "9. RESULTADOS DE LA INSPECCIÓN",
    "10. CONCLUSIONES",
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

MONTHS_ES = {
    1: "ENERO",
    2: "FEBRERO",
    3: "MARZO",
    4: "ABRIL",
    5: "MAYO",
    6: "JUNIO",
    7: "JULIO",
    8: "AGOSTO",
    9: "SEPTIEMBRE",
    10: "OCTUBRE",
    11: "NOVIEMBRE",
    12: "DICIEMBRE",
}

STANDARD_REFERENCES = [
    "B&PV ASME Code 2004. Sec. V. Art. 9. – Visual Testing.",
    "AWS D1.1/D1.1M: 2008 Structural Welding Code Steel.",
    "ASTM E 709 – 01 Standard Practice for Magnetic Particle Examination.",
    "ASTM E 1444 – 01 Standard Guide for Magnetic Particle Examination.",
    "B&PV ASME Code 2004. Sec. V. Art. 7. – Magnetic Testing.",
]

DEFAULT_MT_ITEMS = [
    "Equipo: Yugo Magnético Y7 AC/DC",
    "Serie: F076242 /43560",
    "Equipo: ----",
    "Modelo: P/F",
    "Serie:",
    "Técnica: Baño de Partículas magnéticas marca MAGNAFLUX.",
]

DEFAULT_VT_ITEMS = [
    "Instrumentos de medición:",
    "- Vernier",
    "- Wincha métrica",
    "- Gage",
    "- Cámara fotográfica digital",
    "- Lupa",
    "- Linterna",
]

RESULT_COMPONENT_ORDER = {
    "chasis": 1,
    "puntas_de_ejes": 2,
    "puntas_ejes": 2,
    "balancines": 3,
    "balancines_de_muelles": 3,
    "soportes_de_muelles": 4,
    "cartelas_de_soportes_de_muelles": 4,
    "hojas_de_muelles": 5,
    "bolsas_de_aire": 5,
    "hojas_de_muelles_bolsas_de_aire": 5,
    "templadores": 6,
    "plancha_de_king_pin": 7,
    "plancha_king_pin": 7,
    "king_pin": 8,
    "ejes": 9,
    "munones": 9,
    "muñones": 9,
    "ejes_zona_de_punta_o_munones": 9,
    "ejes_zona_de_punta_o_muñones": 9,
}

SEMIRREMOLQUE_FREQUENCY_ROWS = [
    {"component": "Chasis", "method": "VT", "frequency": "Cada 48,000 Km", "percentage": "100%"},
    {"component": "Balancines de muelles", "method": "VT & MT", "frequency": "Cada 48,000 Km", "percentage": "100%"},
    {"component": "Cartelas de soportes de muelles", "method": "VT & MT", "frequency": "Cada 48,000 Km", "percentage": "100%"},
    {"component": "Templadores", "method": "VT", "frequency": "Cada 48,000 Km", "percentage": "100%"},
    {"component": "King-pin", "method": "VT & MT", "frequency": "Cada 48,000 Km", "percentage": "100%"},
    {"component": "Plancha de King-pin", "method": "VT & MT", "frequency": "Cada 48,000 Km", "percentage": "100%"},
    {"component": "Ejes, zona de punta o muñones", "method": "VT & MT", "frequency": "Cada 48,000 Km", "percentage": "100%"},
]

DEFAULT_CRITERIA = {
    "accepted": (
        "Estructura del chasis, puntas de ejes, planchas de King pin y King pin en buenas "
        "condiciones estructurales, no presenta discontinuidades, desgaste ni deformaciones."
    ),
    "rejected": (
        "Estructura del chasis, puntas de ejes, planchas de King pin y King pin se encuentran "
        "en malas condiciones estructurales."
    ),
    "rejected_items": [
        "Chasis y/o componentes presentan deformaciones, desgaste y discontinuidades en su estructura.",
        "Puntas de ejes presentan desgaste, deformación, discontinuidades y/o presencia de soldadura por reparaciones (no se aceptan reparaciones).",
        "Plancha de King pin presenta desgaste, deformación y/o discontinuidades.",
        "King pin presenta discontinuidades, deformaciones, presencia de soldadura y/o pérdida del diámetro (∅ nominal 50.8 mm, ∅ de retiro 49 mm).",
    ],
    "retirement": "Si el equipo tiene 10 años de antigüedad o 800,000 Km de recorrido.",
}


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


def _format_date_long(value: Any, default: str = "No registrada") -> str:
    if value is None:
        return default
    if not hasattr(value, "day"):
        return _safe_text(value, default)

    day = value.day
    month = MONTHS_ES.get(value.month, "")
    year = value.year
    month_title = month.capitalize() if month else "Mes"
    return f"{day:02d} de {month_title} del {year}"


def _month_upper(value: Any) -> str:
    if value is None or not hasattr(value, "month"):
        return "MES"
    return MONTHS_ES.get(value.month, "MES")


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


def _extract_client_code(requested_by: str) -> str:
    text = _safe_text(requested_by, "CLIENTE")
    direct = re.search(r"\b([A-Z]{2,6})\b", text.upper())
    if direct:
        return direct.group(1)

    tokens = re.findall(r"[A-ZÁÉÍÓÚÑa-záéíóúñ]+", text)
    initials = "".join(token[0] for token in tokens[:4]).upper()
    return initials or "CLI"


def _extract_sequence_from_code(code: str) -> str:
    text = _safe_text(code, "")
    matches = re.findall(r"(\d+)", text)
    if not matches:
        return "001"
    return matches[-1].zfill(3)[-3:]


def _equipment_abbreviation(equipment_type: str) -> str:
    normalized = _normalize_key(equipment_type)
    if "semirremolque" in normalized:
        return "SR"
    if "remolque" in normalized:
        return "RM"
    if "tolva" in normalized:
        return "TV"
    return "EQ"


def _build_report_code_display(inspection: Inspection, field_map: dict[str, str]) -> str:
    inspection_date = getattr(inspection, "inspection_date", None)
    month = _month_upper(inspection_date)
    year = str(getattr(inspection_date, "year", datetime.now().year))

    report_sequence = _find_field(
        field_map,
        ["numero_informe", "correlativo_informe", "report_sequence", "nro_informe", "numero_reporte"],
        default="",
    )
    if not report_sequence:
        report_sequence = _extract_sequence_from_code(_safe_text(getattr(inspection, "code", None), ""))

    requested_by = _safe_text(getattr(inspection, "requested_by", None), _safe_text(getattr(inspection, "client_name", None)))
    client_code = _find_field(field_map, ["sigla_cliente", "client_code"], default="")
    if not client_code:
        client_code = _extract_client_code(requested_by)

    equipment_code = _equipment_abbreviation(_safe_text(getattr(inspection, "equipment_type", None)))
    return f"GS – {month} {year} – {str(report_sequence).zfill(3)} – {equipment_code} - {client_code}"


def _build_methods(evidences: list[Any], transcriptions: list[Any], full_text: str = "") -> list[str]:
    methods = ["INSPECCIÓN VISUAL (VT)"]

    upper_text = (full_text or "").upper()
    if "PARTICULAS MAGNETICAS" in upper_text or "PARTÍCULAS MAGNÉTICAS" in upper_text or "(MT)" in upper_text:
        methods.append("PARTÍCULAS MAGNÉTICAS (MT)")

    has_transcriptions = any(
        bool((getattr(item, "final_text", None) or getattr(item, "raw_text", None) or "").strip())
        for item in transcriptions or []
    )
    if has_transcriptions:
        methods.append("TRANSCRIPCIÓN DE OBSERVACIONES")

    has_ocr = any(
        bool(getattr(item, "ocr_processed", False) or getattr(item, "ocr_extracted_text", None))
        for item in evidences or []
    )
    if has_ocr and "VALIDACIÓN DOCUMENTAL (OCR)" not in methods:
        methods.append("VALIDACIÓN DOCUMENTAL (OCR)")

    deduped: list[str] = []
    for method in methods:
        if method not in deduped:
            deduped.append(method)
    return deduped


def _build_intro_paragraph(
    inspection: Inspection,
    plate: str,
    methods: list[str],
) -> str:
    requested_by = _safe_text(getattr(inspection, "requested_by", None), _safe_text(getattr(inspection, "client_name", None)))
    equipment_type = _safe_text(getattr(inspection, "equipment_type", None))
    inspection_type = _safe_text(getattr(inspection, "inspection_type", None)).lower()
    methods_text = " / ".join(methods)

    plate_text = f" identificado con placa {plate}" if plate != "No registrado" else ""
    return (
        f"A solicitud de la empresa {requested_by}, se ha realizado la inspección {inspection_type} "
        f"del equipo {equipment_type}{plate_text}, empleando los métodos {methods_text}."
    )


def _build_objective(inspection: Inspection, extracted_summary: str) -> str:
    if extracted_summary:
        return extracted_summary

    equipment_type = _safe_text(getattr(inspection, "equipment_type", None))
    normalized = _normalize_key(equipment_type)

    if "semirremolque" in normalized:
        return (
            "Determinar la integridad estructural de los componentes del semirremolque "
            "(chasis, puntas de ejes, plancha de King pin y King pin), mediante inspección "
            "por ensayos no destructivos, con la finalidad de asegurar la confiabilidad del "
            "equipo para una mejor prestación del servicio y así evitar accidentes que "
            "atenten contra la seguridad y el medio ambiente."
        )

    return (
        f"Determinar el estado documentado del equipo {equipment_type} mediante la revisión "
        "de datos estructurados, evidencias registradas y observaciones del inspector, con la "
        "finalidad de emitir un informe técnico uniforme, verificable y trazable."
    )


def _build_scope(
    inspection: Inspection,
    methods: list[str],
    evidences: list[Any],
    transcriptions: list[Any],
) -> list[str]:
    equipment_type = _safe_text(getattr(inspection, "equipment_type", None))
    normalized = _normalize_key(equipment_type)

    items: list[str] = []

    if "semirremolque" in normalized:
        items.append("Inspección visual a toda la estructura del semirremolque para determinar la condición superficial del equipo.")
        if any("MAGNÉTICAS" in method or "(MT)" in method for method in methods):
            items.append("Inspección por partículas magnéticas de las puntas de los ejes, balancines, soportes de muelles, plancha King pin y King pin.")
    else:
        items.append(f"Inspección visual y documental del equipo {equipment_type}.")
        items.append("Verificación del estado general de los componentes críticos y sus uniones estructurales.")

    if evidences:
        items.append("Registro fotográfico y documental de las zonas inspeccionadas.")
    if transcriptions:
        items.append("Incorporación de observaciones transcritas asociadas al proceso de inspección.")

    return items


def _build_protocol(
    inspection: Inspection,
    extracted_protocol: str,
) -> str:
    if extracted_protocol:
        return extracted_protocol

    requested_by = _safe_text(getattr(inspection, "requested_by", None), _safe_text(getattr(inspection, "client_name", None)))
    return (
        f"La presente inspección fue realizada de acuerdo con los criterios técnicos aplicables al servicio solicitado por "
        f"{requested_by}, bajo una metodología estructurada de inspección visual, registro documental, consolidación "
        "de hallazgos y emisión formal de resultados."
    )


def _build_frequency_rows(inspection: Inspection) -> list[dict[str, str]]:
    equipment_type = _safe_text(getattr(inspection, "equipment_type", None))
    normalized = _normalize_key(equipment_type)

    if "semirremolque" in normalized:
        return SEMIRREMOLQUE_FREQUENCY_ROWS.copy()

    return [
        {"component": equipment_type, "method": "VT", "frequency": "Según criticidad operativa", "percentage": "100%"},
    ]


def _build_frequency_note(
    inspection: Inspection,
    field_map: dict[str, str],
    extracted_frequency: str,
) -> str:
    if extracted_frequency:
        return extracted_frequency

    equipment_type = _safe_text(getattr(inspection, "equipment_type", None))
    model = _find_field(field_map, ["modelo", "model", "placa", "plate"], default="No registrado")
    mileage = _find_field(field_map, ["kilometraje", "mileage", "odometro", "odómetro"], default="No registrado")
    age = _find_field(field_map, ["antiguedad", "antigüedad", "age"], default="No registrada")

    normalized = _normalize_key(equipment_type)
    if "semirremolque" in normalized:
        return (
            f"Para el modelo {model}, se recomienda mantener una frecuencia de inspección estructural "
            "cada 48,000 Km para los componentes críticos del semirremolque y no exceder un año entre "
            "inspecciones integrales. Esta periodicidad debe revisarse considerando el kilometraje actual "
            f"({mileage}) y la antigüedad registrada ({age})."
        )

    return (
        f"La frecuencia de inspección del equipo {equipment_type} debe definirse según condición operativa, "
        f"criticidad del servicio, historial de uso y registros disponibles del modelo {model}."
    )


def _build_standards(extracted_standards: str) -> list[str]:
    if extracted_standards:
        lines = [line.strip("•- \t") for line in extracted_standards.splitlines() if line.strip()]
        return lines or STANDARD_REFERENCES.copy()
    return STANDARD_REFERENCES.copy()


def _build_inspection_equipment(
    evidences: list[Any],
    transcriptions: list[Any],
    extracted_equipment: str,
) -> dict[str, list[str]]:
    if extracted_equipment:
        lines = [line.strip() for line in extracted_equipment.splitlines() if line.strip()]
        midpoint = max(1, len(lines) // 2)
        return {
            "mt_title": "Magnetic Testing (MT)",
            "vt_title": "Visual Testing (VT)",
            "mt": lines[:midpoint],
            "vt": lines[midpoint:],
        }

    mt_items = DEFAULT_MT_ITEMS.copy()
    vt_items = DEFAULT_VT_ITEMS.copy()

    if any(bool(getattr(item, "ocr_processed", False)) for item in evidences or []):
        vt_items.append("- Soporte de validación OCR")
    if transcriptions:
        vt_items.append("- Registro de observaciones transcritas")

    return {
        "mt_title": "Magnetic Testing (MT)",
        "vt_title": "Visual Testing (VT)",
        "mt": mt_items,
        "vt": vt_items,
    }


def _build_criteria(extracted_criteria: str) -> dict[str, Any]:
    if extracted_criteria:
        lines = [line.strip() for line in extracted_criteria.splitlines() if line.strip()]
        accepted = ""
        rejected = ""
        rejected_items: list[str] = []
        retirement = ""

        for line in lines:
            upper = line.upper()
            if "ACEPTADO" in upper and not accepted:
                accepted = re.sub(r"^\**\s*ACEPTADO\s*:?\s*", "", line, flags=re.IGNORECASE).strip()
            elif "RECHAZADO" in upper and not rejected:
                rejected = re.sub(r"^\**\s*RECHAZADO\s*:?\s*", "", line, flags=re.IGNORECASE).strip()
            elif "RETIRO" in upper:
                retirement = re.sub(r"^\**\s*RETIRO DE LA OPERACION\s*:?\s*", "", line, flags=re.IGNORECASE).strip()
            else:
                rejected_items.append(line.strip("-• "))

        return {
            "accepted": accepted or DEFAULT_CRITERIA["accepted"],
            "rejected": rejected or DEFAULT_CRITERIA["rejected"],
            "rejected_items": rejected_items or DEFAULT_CRITERIA["rejected_items"],
            "retirement": retirement or DEFAULT_CRITERIA["retirement"],
        }

    return DEFAULT_CRITERIA.copy()


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

    selected = issue_lines if issue_lines else info_lines[:10]
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
        confidence_text = f" | confianza={confidence}" if confidence is not None else ""

        blocks.append(
            "\n".join(
                [
                    f"Transcripción {idx} | idioma={_safe_text(getattr(item, 'language', None), 'No registrado')} | modelo={_safe_text(getattr(item, 'model_name', None), 'No registrado')}{confidence_text}",
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
        1
        for field in fields or []
        if _safe_text(getattr(field, "validation_status", None), "pending").lower() == "mismatch"
    )
    issue_values = sum(
        1 for field in fields or [] if _has_issue_text(_field_best_value(field, default=""))
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
    plate: str,
    fields: list[Any],
    evidences: list[Any],
    transcriptions: list[Any],
    general_condition: str,
) -> str:
    mismatch_count = sum(
        1
        for field in fields or []
        if _safe_text(getattr(field, "validation_status", None), "pending").lower() == "mismatch"
    )
    issue_count = sum(
        1 for field in fields or [] if _has_issue_text(_field_best_value(field, default=""))
    )
    evidence_count = len(evidences or [])
    transcription_count = len([item for item in transcriptions or [] if (item.final_text or item.raw_text or "").strip()])

    equipment_type = _safe_text(getattr(inspection, "equipment_type", None))
    equipment_label = f"{equipment_type} {plate}" if plate != "No registrado" else equipment_type

    if general_condition.upper() == "ACEPTADO":
        return (
            f"El equipo {equipment_label} y sus componentes inspeccionados se encuentran en condición "
            "ACEPTADO para su puesta en operación bajo condiciones normales."
        )

    if issue_count > 0:
        return (
            f"El informe de la inspección {equipment_label} consolida {evidence_count} evidencia(s) y "
            f"{transcription_count} transcripción(es). Se identificaron observaciones técnicas que requieren "
            "validación final del responsable antes de su emisión definitiva."
        )

    if mismatch_count > 0:
        return (
            f"El informe de la inspección {equipment_label} fue construido con datos estructurados y sustento "
            "documental, pero presenta discrepancias OCR en campos críticos, por lo que requiere revisión humana "
            "antes de su aprobación."
        )

    return (
        f"El informe de la inspección {equipment_label} fue construido con la información disponible en el sistema, "
        f"incluyendo {evidence_count} evidencia(s) y {transcription_count} transcripción(es), quedando sujeto a "
        "validación técnica final."
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
        "registrado": "Registrado",
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
    if normalized == "registrado":
        return "Validar en revisión final"
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
    return " | ".join(selected) if selected else "--"


def _humanize_component_name(group_name: str) -> str:
    normalized = _normalize_key(group_name)
    custom = {
        "chasis": "Chasis",
        "puntas_de_ejes": "Puntas de Ejes",
        "puntas_ejes": "Puntas de Ejes",
        "balancines": "Balancines",
        "balancines_de_muelles": "Balancines",
        "soportes_de_muelles": "Soporte de muelles",
        "cartelas_de_soportes_de_muelles": "Soporte de muelles",
        "hojas_de_muelles": "Hojas de muelles/Bolsas de aire",
        "bolsas_de_aire": "Hojas de muelles/Bolsas de aire",
        "hojas_de_muelles_bolsas_de_aire": "Hojas de muelles/Bolsas de aire",
        "templadores": "Templadores",
        "plancha_de_king_pin": "Plancha de King pin",
        "plancha_king_pin": "Plancha de King pin",
        "king_pin": "King pin",
        "ejes": "Ejes",
        "munones": "Muñones",
        "muñones": "Muñones",
        "ejes_zona_de_punta_o_munones": "Ejes, zona de punta o muñones",
        "ejes_zona_de_punta_o_muñones": "Ejes, zona de punta o muñones",
    }
    return custom.get(normalized, _humanize_key(group_name))


def _build_results_rows(
    inspection: Inspection,
    fields: list[Any],
    general_condition: str,
) -> list[dict[str, str]]:
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
        ordered_groups = sorted(
            groups.items(),
            key=lambda item: (
                RESULT_COMPONENT_ORDER.get(_normalize_key(item[0]), 999),
                _humanize_component_name(item[0]),
            ),
        )
        for group_name, group_fields in ordered_groups:
            condition = _derive_group_condition(group_fields)
            rows.append(
                {
                    "equipo": _safe_text(getattr(inspection, "equipment_type", None)),
                    "componente": _humanize_component_name(group_name),
                    "condicion": condition,
                    "observaciones": _build_group_observation(group_fields),
                    "accion": _derive_group_action(condition),
                }
            )

    if not rows:
        normalized_condition = general_condition.upper()
        if normalized_condition == "ACEPTADO":
            default_condition = "Aceptado"
        elif normalized_condition in {"OBSERVADO", "RECHAZADO"}:
            default_condition = "Observado"
        else:
            default_condition = "Registrado"

        default_components = [
            "Chasis",
            "Puntas de Ejes",
            "Balancines",
            "Soporte de muelles",
            "Hojas de muelles/Bolsas de aire",
            "Plancha de King pin",
            "King pin",
        ]

        for component in default_components:
            rows.append(
                {
                    "equipo": _safe_text(getattr(inspection, "equipment_type", None)),
                    "componente": component,
                    "condicion": default_condition,
                    "observaciones": "--",
                    "accion": "--" if default_condition == "Aceptado" else "Validar en revisión final",
                }
            )

    return rows


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

        category = _safe_text(getattr(evidence, "evidence_category", None), "Evidencia general")
        caption = _safe_text(getattr(evidence, "caption", None), f"Foto {idx}")
        display_title = caption if caption != f"Foto {idx}" else f"Foto {idx}. {category}"

        evidences.append(
            {
                "index": idx,
                "path": getattr(evidence, "file_path", None),
                "category": category,
                "caption": caption,
                "display_title": display_title,
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
                "display_title": "Foto 1. Espacio reservado para evidencia fotográfica",
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
        normalized = _normalize_key(explicit)
        if normalized in {"aceptado", "aprobado", "conforme", "ok"}:
            return "ACEPTADO"
        if normalized in {"rechazado"}:
            return "RECHAZADO"
        if normalized in {"observado"}:
            return "OBSERVADO"
        return explicit.upper()

    issue_count = sum(1 for field in fields or [] if _has_issue_text(_field_best_value(field, default="")))
    mismatch_count = sum(
        1
        for field in fields or []
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

    extracted_summary = _extract_section(full_text, ["2. OBJETIVO", "1. RESUMEN EJECUTIVO"], "")
    extracted_scope = _extract_section(full_text, ["3. ALCANCE"], "")
    extracted_protocol = _extract_section(full_text, ["4. PROTOCOLO EMPLEADO"], "")
    extracted_frequency = _extract_section(full_text, ["5. FRECUENCIA DE INSPECCIÓN"], "")
    extracted_standards = _extract_section(full_text, ["6. NORMAS Y CÓDIGOS DE REFERENCIA", "6. NORMAS Y CODIGOS DE REFERENCIA"], "")
    extracted_equipment = _extract_section(full_text, ["7. EQUIPOS DE INSPECCIÓN EMPLEADOS", "7. EQUIPOS DE INSPECCIÓN EMPELADOS"], "")
    extracted_criteria = _extract_section(full_text, ["8. CRITERIOS DE INSPECCIÓN"], "")
    extracted_findings = _extract_section(
        full_text,
        ["9. RESULTADOS DE LA INSPECCIÓN", "3. HALLAZGOS PRINCIPALES", "2. IDENTIFICACIÓN DE CAMPOS CRÍTICOS", "3. DATOS CAPTURADOS EN INSPECCIÓN"],
        "",
    )
    extracted_ocr = _extract_section(full_text, ["4. VALIDACIÓN OCR", "5. VALIDACIÓN OCR"], "")
    extracted_voice = _extract_section(full_text, ["5. OBSERVACIONES TRANSCRITAS", "6. OBSERVACIONES TRANSCRITAS"], "")
    extracted_recommendations = _extract_section(full_text, ["6. RECOMENDACIONES"], "")
    extracted_conclusion = _extract_section(full_text, ["10. CONCLUSIONES", "7. INFORME REDACTADO", "7. CONCLUSIÓN PRELIMINAR"], "")

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
    model_display = plate if plate != "No registrado" else _find_field(field_map, ["modelo", "model"], default=_safe_text(getattr(inspection, "code", None)))

    methods = _build_methods(evidences_raw, transcriptions, full_text)
    general_condition = _infer_general_condition(field_map, fields)
    evidences = _build_evidences(inspection, transcriptions)
    findings = extracted_findings or _build_findings_from_fields(fields)
    ocr_summary = extracted_ocr or _build_ocr_summary_from_fields(fields)
    voice_summary = extracted_voice or _build_voice_summary_from_transcriptions(transcriptions)
    recommendations = extracted_recommendations or _build_recommendations_from_fields(fields, evidences_raw, transcriptions)
    conclusion = extracted_conclusion or _build_conclusion_from_state(
        inspection=inspection,
        plate=plate,
        fields=fields,
        evidences=evidences_raw,
        transcriptions=transcriptions,
        general_condition=general_condition,
    )

    requested_by = _safe_text(getattr(inspection, "requested_by", None), _safe_text(getattr(inspection, "client_name", None)))
    location = _safe_text(getattr(inspection, "location", None), "No registrada")
    inspection_date = getattr(inspection, "inspection_date", None)
    inspection_date_text = _format_date(inspection_date)
    inspection_date_long = _format_date_long(inspection_date)

    intro_paragraph = _build_intro_paragraph(
        inspection=inspection,
        plate=plate,
        methods=methods,
    )

    frequency_rows = _build_frequency_rows(inspection)
    frequency_note = _build_frequency_note(inspection, field_map, extracted_frequency)
    standards = _build_standards(extracted_standards)
    inspection_equipment = _build_inspection_equipment(evidences_raw, transcriptions, extracted_equipment)
    criteria = _build_criteria(extracted_criteria)
    results = _build_results_rows(inspection, fields, general_condition)

    equipment_type = _safe_text(getattr(inspection, "equipment_type", None))
    equipment_label_prefix = equipment_type.upper()
    equipment_display = f"{equipment_label_prefix}: {model_display}"

    context = {
        "draft": draft,
        "inspection": inspection,
        "company": COMPANY_INFO,
        "branding": {
            "logo_path": COMPANY_INFO["logo_path"],
            "report_title": "INFORME FINAL",
            "report_code_display": _build_report_code_display(inspection, field_map),
            "report_subtitle": "ENSAYOS NO DESTRUCTIVOS (END)",
            "equipment_display": equipment_display,
            "divider_lines": True,
        },
        "header": {
            "report_title": "INFORME FINAL",
            "report_code": _safe_text(getattr(inspection, "code", None)),
            "report_code_display": _build_report_code_display(inspection, field_map),
            "report_subtitle": "ENSAYOS NO DESTRUCTIVOS (END)",
            "equipment_display": equipment_display,
            "inspection_type": _safe_text(getattr(inspection, "inspection_type", None), "No registrado").upper(),
            "inspection_date": inspection_date_text,
            "inspection_date_long": inspection_date_long,
            "methods": methods,
            "methods_display": " / ".join(methods),
            "general_condition": general_condition,
            "location": location.upper(),
            "logo_path": COMPANY_INFO["logo_path"],
        },
        "technical_info": {
            "requested_by": requested_by,
            "address": _find_field(field_map, ["direccion", "address", "direccion_cliente"], location),
            "service_responsible": _safe_text(getattr(inspection, "responsible_inspector", None), "Inspector no registrado"),
            "inspection_date_text": inspection_date_text,
            "inspection_date_long": inspection_date_long,
            "intro_paragraph": intro_paragraph,
            "signature_path": "app/static/reports/signatures/firma_responsable.png",
        },
        "identification": {
            "tipo_equipo": equipment_type,
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
        "scope": extracted_scope.splitlines() if extracted_scope else _build_scope(inspection, methods, evidences_raw, transcriptions),
        "protocol": _build_protocol(inspection, extracted_protocol),
        "frequency": frequency_note,
        "frequency_table": frequency_rows,
        "standards": standards,
        "inspection_equipment": inspection_equipment,
        "inspection_equipment_table": inspection_equipment,
        "criteria": criteria,
        "results": results,
        "conclusion": conclusion,
        "ocr_summary": ocr_summary,
        "voice_summary": voice_summary,
        "recommendations": recommendations,
        "evidences": evidences,
        "findings": findings,
        "footer": {
            "company_line": f"{COMPANY_INFO['name']} RUC: {COMPANY_INFO['ruc']}",
            "address_line": COMPANY_INFO["address"],
            "contact_line": f"{COMPANY_INFO['phones']} | {COMPANY_INFO['email']}",
            "website_line": COMPANY_INFO["website"],
            "page_number_template": "{page_number} de {page_count}",
        },
        "document_meta": {
            "show_footer": True,
            "show_dividers": True,
            "show_cover_logo": True,
            "render_results_table": True,
            "render_evidence_gallery": True,
        },
    }

    return context