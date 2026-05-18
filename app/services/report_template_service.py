import re
import unicodedata
from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session, selectinload

from app.db.models import Inspection, ReportDraft, Transcription

COMPANY_LOGO_PATH = "app/static/reports/global_supplier_logo.png"
COMPANYLOGOPATH = COMPANY_LOGO_PATH

FIXED_EVIDENCE_SECTIONS = [
    {
        "section_key": "identificacion_documental",
        "section_title": "Identificación documental",
        "slots": [
            ("cover_semitrailer", "Vista general del semirremolque"),
            ("plate_vehicle", "Placa vehicular"),
            ("plate_technical", "Placa técnica / placa de fabricación"),
        ],
    },
    {
        "section_key": "kingpin",
        "section_title": "Sistema King Pin",
        "slots": [
            ("kingpin_subject", "King Pin inspeccionado"),
            ("kingpin_reference", "King Pin de referencia"),
            ("kingpin_plate_subject", "Plancha de King Pin"),
        ],
    },
    {
        "section_key": "tren_rodante",
        "section_title": "Tren rodante por eje",
        "dynamic_axle_slots": [
            ("journal", "Muñón"),
            ("axle_end", "Punta de eje"),
        ],
    },
]
FIXEDEVIDENCESECTIONS = FIXED_EVIDENCE_SECTIONS

COMPANY_INFO = {
    "name": "GLOBAL SUPPLIER S&P SAC.",
    "ruc": "20477372571",
    "address": "Av. José María Eguren Sur 266 Int. 2 Urb. Palermo - Trujillo-Perú.",
    "phones": "Tel: 044-652077 cel. 923281042 - 965382425",
    "email": "ventas@globalsuppliersp.com",
    "website": "www.globalsuppliersp.com",
    "logo_path": COMPANY_LOGO_PATH,
    "logopath": COMPANY_LOGO_PATH,
}
COMPANYINFO = COMPANY_INFO

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
SECTIONMARKERS = SECTION_MARKERS

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
ISSUEKEYWORDS = ISSUE_KEYWORDS

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
MONTHSES = MONTHS_ES

STANDARD_REFERENCES = [
    "B&PV ASME Code 2004. Sec. V. Art. 9. – Visual Testing.",
    "AWS D1.1/D1.1M: 2008 Structural Welding Code Steel.",
    "ASTM E 709 – 01 Standard Practice for Magnetic Particle Examination.",
    "ASTM E 1444 – 01 Standard Guide for Magnetic Particle Examination.",
    "B&PV ASME Code 2004. Sec. V. Art. 7. – Magnetic Testing.",
]
STANDARDREFERENCES = STANDARD_REFERENCES

DEFAULT_MT_ITEMS = [
    "Equipo: Yugo Magnético Y7 AC/DC",
    "Serie: F076242 /43560",
    "Equipo: ----",
    "Modelo: P/F",
    "Serie:",
    "Técnica: Baño de Partículas magnéticas marca MAGNAFLUX.",
]
DEFAULTMTITEMS = DEFAULT_MT_ITEMS

DEFAULT_VT_ITEMS = [
    "Instrumentos de medición:",
    "- Vernier",
    "- Wincha métrica",
    "- Gage",
    "- Cámara fotográfica digital",
    "- Lupa",
    "- Linterna",
]
DEFAULTVTITEMS = DEFAULT_VT_ITEMS

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
RESULTCOMPONENTORDER = RESULT_COMPONENT_ORDER

SEMIRREMOLQUE_FREQUENCY_ROWS = [
    {"component": "Chasis", "method": "VT", "frequency": "Cada 48,000 Km", "percentage": "100%"},
    {"component": "Balancines de muelles", "method": "VT & MT", "frequency": "Cada 48,000 Km", "percentage": "100%"},
    {"component": "Cartelas de soportes de muelles", "method": "VT & MT", "frequency": "Cada 48,000 Km", "percentage": "100%"},
    {"component": "Templadores", "method": "VT", "frequency": "Cada 48,000 Km", "percentage": "100%"},
    {"component": "King-pin", "method": "VT & MT", "frequency": "Cada 48,000 Km", "percentage": "100%"},
    {"component": "Plancha de King-pin", "method": "VT & MT", "frequency": "Cada 48,000 Km", "percentage": "100%"},
    {"component": "Ejes, zona de punta o muñones", "method": "VT & MT", "frequency": "Cada 48,000 Km", "percentage": "100%"},
]
SEMIRREMOLQUEFREQUENCYROWS = SEMIRREMOLQUE_FREQUENCY_ROWS

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
DEFAULTCRITERIA = DEFAULT_CRITERIA


def _get_attr(obj: Any, *names: str, default: Any = None) -> Any:
    if obj is None:
        return default
    for name in names:
        if hasattr(obj, name):
            value = getattr(obj, name)
            if value is not None:
                return value
    return default


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def safe_text(value: Any, default: str = "No registrado") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def format_date(value: Any, default: str = "No registrada") -> str:
    if value is None:
        return default
    if hasattr(value, "strftime"):
        return value.strftime("%d/%m/%Y")
    text = str(value).strip()
    return text if text else default


def format_date_long(value: Any, default: str = "No registrada") -> str:
    if value is None:
        return default
    if not hasattr(value, "day"):
        return safe_text(value, default)

    day = value.day
    month = MONTHS_ES.get(value.month, "")
    year = value.year
    month_title = month.capitalize() if month else "Mes"
    return f"{day:02d} de {month_title} del {year}"


def month_upper(value: Any) -> str:
    if value is None or not hasattr(value, "month"):
        return "MES"
    return MONTHS_ES.get(value.month, "MES")


def normalize_key(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def humanize_key(value: str | None) -> str:
    normalized = normalize_key(value)
    if not normalized:
        return "Componente"
    return normalized.replace("_", " ").title()


def pick_attr(obj: Any, candidates: list[str], default: str = "No registrado") -> str:
    for name in candidates:
        value = _get_attr(obj, name)
        if value is None:
            continue
        if hasattr(value, "strftime"):
            return format_date(value, default)
        text = str(value).strip()
        if text:
            return text
    return default


def field_best_value(field: Any, default: str = "No registrado") -> str:
    for attr in ("finalvalue", "final_value", "manualvalue", "manual_value", "ocrvalue", "ocr_value"):
        value = _get_attr(field, attr)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def draft_text(draft: ReportDraft | None) -> str:
    if not draft:
        return ""
    return safe_text(
        _get_attr(draft, "editedtext", "edited_text", default=None)
        or _get_attr(draft, "generatedtext", "generated_text", default=None),
        "",
    )


def extract_section(text: str, headings: list[str], fallback: str = "") -> str:
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


def has_issue_text(value: str | None) -> bool:
    normalized = normalize_key(value or "")
    if not normalized:
        return False
    normalized_text = normalized.replace("_", " ")
    return any(keyword in normalized_text for keyword in ISSUE_KEYWORDS)


def get_field_map(inspection: Inspection) -> dict[str, str]:
    data: dict[str, str] = {}
    for field in getattr(inspection, "fields", []) or []:
        value = field_best_value(field, default="")
        if not value:
            continue

        field_key = normalize_key(_get_attr(field, "fieldkey", "field_key"))
        field_label = normalize_key(_get_attr(field, "fieldlabel", "field_label"))

        if field_key:
            data[field_key] = value
        if field_label:
            data[field_label] = value
    return data


def find_field(field_map: dict[str, str], aliases: list[str], default: str = "No registrado") -> str:
    for alias in aliases:
        key = normalize_key(alias)
        value = field_map.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def evidence_best_title(evidence: Any, fallback: str) -> str:
    caption = _get_attr(evidence, "caption")
    raw_label = _get_attr(evidence, "rawlabel", "raw_label")
    normalized_label = _get_attr(evidence, "normalizedlabel", "normalized_label")
    return safe_text(caption or raw_label or normalized_label, fallback)


def build_evidence_slot_map(evidences: list[Any]) -> dict[str, Any]:
    slot_map: dict[str, Any] = {}
    for evidence in evidences or []:
        slot = _get_attr(evidence, "evidenceslot", "evidence_slot")
        if slot and slot not in slot_map:
            slot_map[slot] = evidence
    return slot_map


def build_dynamic_axle_slot_name(component_code: str, axle_number: int, side: str) -> str:
    if component_code == "journal":
        return f"journal_{axle_number}_{side}"
    if component_code == "axle_end":
        return f"axle_{axle_number}_{side}_end"
    return f"{component_code}_{axle_number}_{side}"


def serialize_evidence_for_slot(evidence: Any, slot_label: str, slot_key: str) -> dict[str, Any]:
    if not evidence:
        return {
            "slot_key": slot_key,
            "slotkey": slot_key,
            "slot_label": slot_label,
            "slotlabel": slot_label,
            "present": False,
            "filepath": None,
            "file_path": None,
            "caption": "No registrada",
            "filetype": "No registrado",
            "file_type": "No registrado",
            "ocrtext": "",
            "ocr_text": "",
            "evidencecategory": "No registrado",
            "evidence_category": "No registrado",
        }

    file_path = _get_attr(evidence, "filepath", "file_path")
    file_type = safe_text(_get_attr(evidence, "filetype", "file_type"))
    ocr_text = safe_text(_get_attr(evidence, "ocrextractedtext", "ocr_extracted_text"), "")
    evidence_category = safe_text(_get_attr(evidence, "evidencecategory", "evidence_category"))

    return {
        "slot_key": slot_key,
        "slotkey": slot_key,
        "slot_label": slot_label,
        "slotlabel": slot_label,
        "present": True,
        "filepath": file_path,
        "file_path": file_path,
        "caption": evidence_best_title(evidence, slot_label),
        "filetype": file_type,
        "file_type": file_type,
        "ocrtext": ocr_text,
        "ocr_text": ocr_text,
        "evidencecategory": evidence_category,
        "evidence_category": evidence_category,
    }


def build_fixed_evidence_sections(evidences: list[Any]) -> list[dict[str, Any]]:
    slot_map = build_evidence_slot_map(evidences)
    sections: list[dict[str, Any]] = []

    detected_axles = sorted(
        {
            axle
            for item in evidences or []
            for axle in [_get_attr(item, "axlenumber", "axle_number")]
            if axle is not None and int(axle) >= 1
        }
    )

    for section in FIXED_EVIDENCE_SECTIONS:
        rows: list[dict[str, Any]] = []

        for slot_key, slot_label in section.get("slots", []):
            rows.append(
                serialize_evidence_for_slot(
                    slot_map.get(slot_key),
                    slot_label=slot_label,
                    slot_key=slot_key,
                )
            )

        dynamic_axle_slots = section.get("dynamic_axle_slots", [])
        if dynamic_axle_slots:
            for axle_number in detected_axles:
                for side in ("left", "right"):
                    for component_code, base_label in dynamic_axle_slots:
                        dynamic_slot_key = build_dynamic_axle_slot_name(
                            component_code=component_code,
                            axle_number=axle_number,
                            side=side,
                        )
                        side_label = "Izquierdo" if side == "left" else "Derecho"
                        dynamic_slot_label = f"{base_label} eje {int(axle_number)} {side_label}"
                        rows.append(
                            serialize_evidence_for_slot(
                                slot_map.get(dynamic_slot_key),
                                slot_label=dynamic_slot_label,
                                slot_key=dynamic_slot_key,
                            )
                        )

        sections.append(
            {
                "section_key": section["section_key"],
                "sectionkey": section["section_key"],
                "section_title": section["section_title"],
                "sectiontitle": section["section_title"],
                "items": rows,
            }
        )

    return sections


def build_evidence_section_by_slots(evidences: list[Any]) -> str:
    sections = build_fixed_evidence_sections(evidences)
    if not sections:
        return "No se registraron evidencias asociadas."

    lines: list[str] = []
    for section in sections:
        lines.append(section["section_title"])
        for item in section["items"]:
            if item["present"]:
                lines.append(
                    f"- {item['slot_label']}: OK | categoría {item['evidence_category']} | "
                    f"tipo {item['file_type']} | ruta {safe_text(item['filepath'], 'Sin ruta')} | "
                    f"descripción {item['caption']} | OCR {safe_text(item['ocr_text'], 'Sin OCR')}"
                )
            else:
                lines.append(f"- {item['slot_label']}: PENDIENTE")
        lines.append("")

    return "\n".join(lines).strip()


def extract_client_code(requested_by: str) -> str:
    text = safe_text(requested_by, "CLIENTE")
    direct = re.search(r"\b([A-Z]{2,6})\b", text.upper())
    if direct:
        return direct.group(1)

    tokens = re.findall(r"[A-ZÁÉÍÓÚÑa-záéíóúñ]+", text)
    initials = "".join(token[0] for token in tokens[:4]).upper()
    return initials or "CLI"


def extract_sequence_from_code(code: str) -> str:
    text = safe_text(code, "")
    matches = re.findall(r"(\d+)", text)
    if not matches:
        return "001"
    return matches[-1].zfill(3)[-3:]


def equipment_abbreviation(equipment_type: str) -> str:
    normalized = normalize_key(equipment_type)
    if "semirremolque" in normalized:
        return "SR"
    if "remolque" in normalized:
        return "RM"
    if "tolva" in normalized:
        return "TV"
    return "EQ"


def build_report_code_display(inspection: Inspection, field_map: dict[str, str]) -> str:
    inspection_date = _get_attr(inspection, "inspectiondate", "inspection_date")
    month = month_upper(inspection_date)
    year = str(getattr(inspection_date, "year", datetime.now().year))

    report_sequence = find_field(
        field_map,
        ["numero_informe", "correlativo_informe", "report_sequence", "nro_informe", "numero_reporte"],
        default="",
    )
    if not report_sequence:
        report_sequence = extract_sequence_from_code(safe_text(_get_attr(inspection, "code"), ""))

    requested_by = safe_text(
        _get_attr(inspection, "requestedby", "requested_by"),
        safe_text(_get_attr(inspection, "clientname", "client_name")),
    )
    client_code = find_field(field_map, ["sigla_cliente", "client_code"], default="")
    if not client_code:
        client_code = extract_client_code(requested_by)

    equipment_code = equipment_abbreviation(safe_text(_get_attr(inspection, "equipmenttype", "equipment_type")))
    return f"GS – {month} {year} – {str(report_sequence).zfill(3)} – {equipment_code} - {client_code}"


def build_methods(evidences: list[Any], transcriptions: list[Any], full_text: str = "") -> list[str]:
    methods = ["INSPECCIÓN VISUAL (VT)"]

    upper_text = (full_text or "").upper()
    if "PARTICULAS MAGNETICAS" in upper_text or "PARTÍCULAS MAGNÉTICAS" in upper_text or "(MT)" in upper_text:
        methods.append("PARTÍCULAS MAGNÉTICAS (MT)")

    has_transcriptions = any(
        bool((safe_text(_get_attr(item, "finaltext", "final_text", default=None), "") or safe_text(_get_attr(item, "rawtext", "raw_text", default=None), "")).strip())
        for item in transcriptions or []
    )
    if has_transcriptions:
        methods.append("TRANSCRIPCIÓN DE OBSERVACIONES")

    has_ocr = any(
        bool(_get_attr(item, "ocrprocessed", "ocr_processed", default=False) or _get_attr(item, "ocrextractedtext", "ocr_extracted_text", default=None))
        for item in evidences or []
    )
    if has_ocr and "VALIDACIÓN DOCUMENTAL (OCR)" not in methods:
        methods.append("VALIDACIÓN DOCUMENTAL (OCR)")

    deduped: list[str] = []
    for method in methods:
        if method not in deduped:
            deduped.append(method)
    return deduped


def build_intro_paragraph(inspection: Inspection, plate: str, methods: list[str]) -> str:
    requested_by = safe_text(
        _get_attr(inspection, "requestedby", "requested_by"),
        safe_text(_get_attr(inspection, "clientname", "client_name")),
    )
    equipment_type = safe_text(_get_attr(inspection, "equipmenttype", "equipment_type"))
    inspection_type = safe_text(_get_attr(inspection, "inspectiontype", "inspection_type")).lower()
    methods_text = " / ".join(methods)
    plate_text = f" identificado con placa {plate}" if plate != "No registrado" else ""

    return (
        f"A solicitud de la empresa {requested_by}, se ha realizado la inspección {inspection_type} "
        f"del equipo {equipment_type}{plate_text}, empleando los métodos {methods_text}."
    )

def build_objective(inspection: Inspection, extracted_objective: str) -> str:
    if extracted_objective:
        return extracted_objective

    equipment_type = safe_text(_get_attr(inspection, "equipmenttype", "equipment_type"))
    normalized = normalize_key(equipment_type)

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

def build_scope(
    inspection: Inspection,
    methods: list[str],
    evidences: list[Any],
    transcriptions: list[Any],
) -> list[str]:
    equipment_type = safe_text(_get_attr(inspection, "equipmenttype", "equipment_type"))
    normalized = normalize_key(equipment_type)

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

def build_protocol(inspection: Inspection, extracted_protocol: str) -> str:
    if extracted_protocol:
        return extracted_protocol

    requested_by = safe_text(
        _get_attr(inspection, "requestedby", "requested_by"),
        safe_text(_get_attr(inspection, "clientname", "client_name")),
    )
    return (
        f"La presente inspección fue realizada de acuerdo con los criterios técnicos aplicables al servicio solicitado por "
        f"{requested_by}, bajo una metodología estructurada de inspección visual, registro documental, consolidación "
        "de hallazgos y emisión formal de resultados."
    )

def build_frequency_rows(inspection: Inspection) -> list[dict[str, str]]:
    equipment_type = safe_text(_get_attr(inspection, "equipmenttype", "equipment_type"))
    normalized = normalize_key(equipment_type)

    if "semirremolque" in normalized:
        return SEMIRREMOLQUE_FREQUENCY_ROWS.copy()

    return [
        {"component": equipment_type, "method": "VT", "frequency": "Según criticidad operativa", "percentage": "100%"},
    ]


def build_frequency_note(inspection: Inspection, field_map: dict[str, str], extracted_frequency: str) -> str:
    if extracted_frequency:
        return extracted_frequency

    equipment_type = safe_text(_get_attr(inspection, "equipmenttype", "equipment_type"))
    model = find_field(field_map, ["modelo", "model", "placa", "plate"], default="No registrado")
    mileage = find_field(field_map, ["kilometraje", "mileage", "odometro", "odómetro"], default="No registrado")
    age = find_field(field_map, ["antiguedad", "antigüedad", "age"], default="No registrada")

    normalized = normalize_key(equipment_type)
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


def build_standards(extracted_standards: str) -> list[str]:
    if extracted_standards:
        lines = [line.strip("•- \t") for line in extracted_standards.splitlines() if line.strip()]
        return lines or STANDARD_REFERENCES.copy()
    return STANDARD_REFERENCES.copy()


def build_inspection_equipment(
    evidences: list[Any],
    transcriptions: list[Any],
    extracted_equipment: str,
) -> dict[str, list[str] | str]:
    if extracted_equipment:
        lines = [line.strip() for line in extracted_equipment.splitlines() if line.strip()]
        midpoint = max(1, len(lines) // 2)
        return {
            "mt_title": "Magnetic Testing (MT)",
            "mttitle": "Magnetic Testing (MT)",
            "vt_title": "Visual Testing (VT)",
            "vttitle": "Visual Testing (VT)",
            "mt": lines[:midpoint],
            "vt": lines[midpoint:],
        }

    mt_items = DEFAULT_MT_ITEMS.copy()
    vt_items = DEFAULT_VT_ITEMS.copy()

    if any(bool(_get_attr(item, "ocrprocessed", "ocr_processed", default=False)) for item in evidences or []):
        vt_items.append("- Soporte de validación OCR")
    if transcriptions:
        vt_items.append("- Registro de observaciones transcritas")

    return {
        "mt_title": "Magnetic Testing (MT)",
        "mttitle": "Magnetic Testing (MT)",
        "vt_title": "Visual Testing (VT)",
        "vttitle": "Visual Testing (VT)",
        "mt": mt_items,
        "vt": vt_items,
    }


def build_criteria(extracted_criteria: str) -> dict[str, Any]:
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
            "rejecteditems": rejected_items or DEFAULT_CRITERIA["rejected_items"],
            "retirement": retirement or DEFAULT_CRITERIA["retirement"],
        }

    return {
        "accepted": DEFAULT_CRITERIA["accepted"],
        "rejected": DEFAULT_CRITERIA["rejected"],
        "rejected_items": DEFAULT_CRITERIA["rejected_items"],
        "rejecteditems": DEFAULT_CRITERIA["rejected_items"],
        "retirement": DEFAULT_CRITERIA["retirement"],
    }


def build_findings_from_fields(fields: list[Any]) -> str:
    if not fields:
        return "No se registraron hallazgos específicos."

    issue_lines: list[str] = []
    info_lines: list[str] = []

    for field in fields:
        label = safe_text(_get_attr(field, "fieldlabel", "field_label"), safe_text(_get_attr(field, "fieldkey", "field_key"), "Campo"))
        value = field_best_value(field, default="")
        if not value:
            continue

        line = f"- {label}: {value}"
        status = safe_text(_get_attr(field, "validationstatus", "validation_status"), "pending").lower()
        message = safe_text(_get_attr(field, "validationmessage", "validation_message"), "")

        if has_issue_text(value) or status in {"mismatch", "notfound", "not_found"}:
            if message:
                line = f"{line} ({message})"
            issue_lines.append(line)
        else:
            info_lines.append(line)

    selected = issue_lines if issue_lines else info_lines[:10]
    return "\n".join(selected) if selected else "No se registraron hallazgos específicos."


def build_ocr_summary_from_fields(fields: list[Any]) -> str:
    if not fields:
        return "No hay resultados OCR asociados."

    matched = 0
    mismatched = 0
    not_found = 0
    pending = 0
    details: list[str] = []

    for field in fields:
        status = safe_text(_get_attr(field, "validationstatus", "validation_status"), "pending").lower()
        label = safe_text(_get_attr(field, "fieldlabel", "field_label"), safe_text(_get_attr(field, "fieldkey", "field_key"), "Campo"))
        manual_value = safe_text(_get_attr(field, "manualvalue", "manual_value"))
        ocr_value = safe_text(_get_attr(field, "ocrvalue", "ocr_value"))
        message = safe_text(_get_attr(field, "validationmessage", "validation_message"), "")

        if status == "matched":
            matched += 1
        elif status in {"mismatch", "mismatched"}:
            mismatched += 1
        elif status in {"notfound", "not_found"}:
            not_found += 1
        else:
            pending += 1

        if status in {"mismatch", "mismatched", "notfound", "not_found"}:
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


def build_voice_summary_from_transcriptions(transcriptions: list[Transcription]) -> str:
    if not transcriptions:
        return "No se registraron transcripciones asociadas."

    blocks: list[str] = []
    for idx, item in enumerate(transcriptions, start=1):
        text = safe_text(
            _get_attr(item, "finaltext", "final_text", default=None)
            or _get_attr(item, "rawtext", "raw_text", default=None),
            "",
        )
        if not text:
            continue

        confidence = _to_float(_get_attr(item, "confidence"))
        confidence_text = f" | confianza={confidence}" if confidence is not None else ""

        blocks.append(
            "\n".join(
                [
                    f"Transcripción {idx} | idioma={safe_text(_get_attr(item, 'language'), 'No registrado')} | modelo={safe_text(_get_attr(item, 'modelname', 'model_name'), 'No registrado')}{confidence_text}",
                    text,
                ]
            )
        )

    return "\n\n".join(blocks) if blocks else "No se registraron transcripciones asociadas."


def build_recommendations_from_fields(fields: list[Any], evidences: list[Any], transcriptions: list[Any]) -> str:
    mismatches = sum(
        1
        for field in fields or []
        if safe_text(_get_attr(field, "validationstatus", "validation_status"), "pending").lower() in {"mismatch", "mismatched"}
    )
    issue_values = sum(1 for field in fields or [] if has_issue_text(field_best_value(field, default="")))

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


def build_conclusion_from_state(
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
        if safe_text(_get_attr(field, "validationstatus", "validation_status"), "pending").lower() in {"mismatch", "mismatched"}
    )
    issue_count = sum(1 for field in fields or [] if has_issue_text(field_best_value(field, default="")))
    evidence_count = len(evidences or [])
    transcription_count = len(
        [
            item
            for item in transcriptions or []
            if safe_text(
                _get_attr(item, "finaltext", "final_text", default=None)
                or _get_attr(item, "rawtext", "raw_text", default=None),
                "",
            )
        ]
    )

    equipment_type = safe_text(_get_attr(inspection, "equipmenttype", "equipment_type"))
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


def derive_group_condition(group_fields: list[Any]) -> str:
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
        key = normalize_key(_get_attr(field, "fieldkey", "field_key"))
        if "condicion" in key or "estado" in key or "resultado" in key:
            value = field_best_value(field, default="")
            normalized = normalize_key(value).replace("_", " ")
            for alias, mapped in explicit_condition_aliases.items():
                if alias in normalized:
                    return mapped

    issue_detected = any(has_issue_text(field_best_value(field, default="")) for field in group_fields)
    mismatch_detected = any(
        safe_text(_get_attr(field, "validationstatus", "validation_status"), "pending").lower() in {"mismatch", "mismatched"}
        for field in group_fields
    )
    pending_detected = any(
        safe_text(_get_attr(field, "validationstatus", "validation_status"), "pending").lower() in {"pending", "notfound", "not_found", "notevaluated", "not_evaluated"}
        for field in group_fields
    )

    if issue_detected or mismatch_detected:
        return "Observado"
    if pending_detected:
        return "Pendiente"
    return "Registrado"


def derive_group_action(condition: str) -> str:
    normalized = normalize_key(condition)
    if normalized in {"observado", "rechazado"}:
        return "Revisar y definir acción correctiva"
    if normalized == "pendiente":
        return "Completar revisión técnica"
    if normalized == "aceptado":
        return "--"
    return "Validar en revisión final"


def truncate(value: str, max_len: int = 140) -> str:
    text = safe_text(value, "")
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."


def build_group_observation(group_fields: list[Any]) -> str:
    issue_lines: list[str] = []
    normal_lines: list[str] = []

    for field in group_fields:
        label = safe_text(_get_attr(field, "fieldlabel", "field_label"), safe_text(_get_attr(field, "fieldkey", "field_key"), "Campo"))
        value = field_best_value(field, default="")
        if not value:
            continue

        line = f"{label}: {truncate(value, 90)}"
        if has_issue_text(value):
            issue_lines.append(line)
        else:
            normal_lines.append(line)

    selected = issue_lines[:2] if issue_lines else normal_lines[:2]
    return " | ".join(selected) if selected else "--"


def humanize_component_name(group_name: str) -> str:
    normalized = normalize_key(group_name)
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
    return custom.get(normalized, humanize_key(group_name))


def build_results_rows(inspection: Inspection, fields: list[Any], general_condition: str) -> list[dict[str, str]]:
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
        group = normalize_key(_get_attr(field, "fieldgroup", "field_group"))
        if not group or group in ignored_groups:
            continue
        groups[group].append(field)

    rows: list[dict[str, str]] = []

    if groups:
        ordered_groups = sorted(
            groups.items(),
            key=lambda item: (
                RESULT_COMPONENT_ORDER.get(normalize_key(item[0]), 999),
                humanize_component_name(item[0]),
            ),
        )
        for group_name, group_fields in ordered_groups:
            condition = derive_group_condition(group_fields)
            rows.append(
                {
                    "equipo": safe_text(_get_attr(inspection, "equipmenttype", "equipment_type")),
                    "componente": humanize_component_name(group_name),
                    "condicion": condition,
                    "observaciones": build_group_observation(group_fields),
                    "accion": derive_group_action(condition),
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
                    "equipo": safe_text(_get_attr(inspection, "equipmenttype", "equipment_type")),
                    "componente": component,
                    "condicion": default_condition,
                    "observaciones": "--",
                    "accion": "--" if default_condition == "Aceptado" else "Validar en revisión final",
                }
            )

    return rows


def build_evidences(inspection: Inspection, transcriptions: list[Transcription]) -> list[dict[str, Any]]:
    evidence_transcription_map: dict[int, list[str]] = defaultdict(list)
    for item in transcriptions or []:
        evidence_id = _get_attr(item, "evidenceid", "evidence_id")
        if evidence_id is None:
            continue

        text = safe_text(
            _get_attr(item, "finaltext", "final_text", default=None)
            or _get_attr(item, "rawtext", "raw_text", default=None),
            "",
        )
        if text:
            evidence_transcription_map[evidence_id].append(text)

    evidences: list[dict[str, Any]] = []
    for idx, evidence in enumerate(getattr(inspection, "evidences", []) or [], start=1):
        evidence_id = _get_attr(evidence, "id")
        linked_transcriptions = evidence_transcription_map.get(evidence_id, [])

        ocr_text = safe_text(_get_attr(evidence, "ocrextractedtext", "ocr_extracted_text"), "")
        if linked_transcriptions:
            transcribed_block = " | ".join(linked_transcriptions[:2])
            ocr_text = f"{ocr_text}\n{transcribed_block}".strip() if ocr_text else transcribed_block

        category = safe_text(_get_attr(evidence, "evidencecategory", "evidence_category"), "Evidencia general")
        caption = safe_text(_get_attr(evidence, "caption"), f"Foto {idx}")
        display_title = caption if caption != f"Foto {idx}" else f"Foto {idx}. {category}"
        file_path = _get_attr(evidence, "filepath", "file_path")
        file_type = _get_attr(evidence, "filetype", "file_type")
        evidence_slot = _get_attr(evidence, "evidenceslot", "evidence_slot")
        component_code = _get_attr(evidence, "componentcode", "component_code")
        axle_number = _get_attr(evidence, "axlenumber", "axle_number")
        side = _get_attr(evidence, "side")
        is_reference = bool(_get_attr(evidence, "isreference", "is_reference", default=False))
        ocr_confidence = _to_float(_get_attr(evidence, "ocrconfidence", "ocr_confidence"))
        ocr_processed = bool(_get_attr(evidence, "ocrprocessed", "ocr_processed", default=False))

        evidences.append(
            {
                "index": idx,
                "evidenceid": evidence_id,
                "evidence_id": evidence_id,
                "path": file_path,
                "filepath": file_path,
                "file_path": file_path,
                "filetype": file_type,
                "file_type": file_type,
                "evidencecategory": _get_attr(evidence, "evidencecategory", "evidence_category"),
                "evidence_category": _get_attr(evidence, "evidencecategory", "evidence_category"),
                "caption": _get_attr(evidence, "caption"),
                "rawlabel": _get_attr(evidence, "rawlabel", "raw_label"),
                "raw_label": _get_attr(evidence, "rawlabel", "raw_label"),
                "normalizedlabel": _get_attr(evidence, "normalizedlabel", "normalized_label"),
                "normalized_label": _get_attr(evidence, "normalizedlabel", "normalized_label"),
                "evidenceslot": evidence_slot,
                "evidence_slot": evidence_slot,
                "componentcode": component_code,
                "component_code": component_code,
                "axlenumber": axle_number,
                "axle_number": axle_number,
                "side": side,
                "isreference": is_reference,
                "is_reference": is_reference,
                "ocrextractedtext": _get_attr(evidence, "ocrextractedtext", "ocr_extracted_text"),
                "ocr_extracted_text": _get_attr(evidence, "ocrextractedtext", "ocr_extracted_text"),
                "ocrconfidence": ocr_confidence,
                "ocr_confidence": ocr_confidence,
                "ocrprocessed": ocr_processed,
                "ocr_processed": ocr_processed,
                "ocrtext": ocr_text,
                "ocr_text": ocr_text,
                "category": category,
                "displaytitle": display_title,
                "display_title": display_title,
            }
        )

    if not evidences:
        evidences = [
            {
                "index": 1,
                "path": None,
                "filepath": None,
                "file_path": None,
                "category": "Evidencia pendiente",
                "evidencecategory": "Evidencia pendiente",
                "evidence_category": "Evidencia pendiente",
                "caption": "Espacio reservado para evidencia fotográfica",
                "displaytitle": "Foto 1. Espacio reservado para evidencia fotográfica",
                "display_title": "Foto 1. Espacio reservado para evidencia fotográfica",
                "ocrtext": "",
                "ocr_text": "",
                "filetype": "No registrado",
                "file_type": "No registrado",
                "ocrprocessed": False,
                "ocr_processed": False,
            }
        ]

    return evidences


def serialize_field(field: Any) -> dict[str, Any]:
    return {
        "fieldid": _get_attr(field, "id"),
        "field_id": _get_attr(field, "id"),
        "fieldkey": _get_attr(field, "fieldkey", "field_key"),
        "field_key": _get_attr(field, "fieldkey", "field_key"),
        "fieldlabel": _get_attr(field, "fieldlabel", "field_label"),
        "field_label": _get_attr(field, "fieldlabel", "field_label"),
        "fieldgroup": _get_attr(field, "fieldgroup", "field_group"),
        "field_group": _get_attr(field, "fieldgroup", "field_group"),
        "expectedtype": _get_attr(field, "expectedtype", "expected_type"),
        "expected_type": _get_attr(field, "expectedtype", "expected_type"),
        "manualvalue": _get_attr(field, "manualvalue", "manual_value"),
        "manual_value": _get_attr(field, "manualvalue", "manual_value"),
        "ocrvalue": _get_attr(field, "ocrvalue", "ocr_value"),
        "ocr_value": _get_attr(field, "ocrvalue", "ocr_value"),
        "finalvalue": _get_attr(field, "finalvalue", "final_value"),
        "final_value": _get_attr(field, "finalvalue", "final_value"),
        "validationstatus": _get_attr(field, "validationstatus", "validation_status"),
        "validation_status": _get_attr(field, "validationstatus", "validation_status"),
        "validationmessage": _get_attr(field, "validationmessage", "validation_message"),
        "validation_message": _get_attr(field, "validationmessage", "validation_message"),
        "confidence": _to_float(_get_attr(field, "confidence")),
    }


def serialize_transcription(item: Any) -> dict[str, Any]:
    return {
        "transcriptionid": _get_attr(item, "id"),
        "transcription_id": _get_attr(item, "id"),
        "inspectionid": _get_attr(item, "inspectionid", "inspection_id"),
        "inspection_id": _get_attr(item, "inspectionid", "inspection_id"),
        "evidenceid": _get_attr(item, "evidenceid", "evidence_id"),
        "evidence_id": _get_attr(item, "evidenceid", "evidence_id"),
        "sourcefilepath": _get_attr(item, "sourcefilepath", "source_file_path"),
        "source_file_path": _get_attr(item, "sourcefilepath", "source_file_path"),
        "language": _get_attr(item, "language"),
        "modelname": _get_attr(item, "modelname", "model_name"),
        "model_name": _get_attr(item, "modelname", "model_name"),
        "rawtext": _get_attr(item, "rawtext", "raw_text"),
        "raw_text": _get_attr(item, "rawtext", "raw_text"),
        "finaltext": _get_attr(item, "finaltext", "final_text"),
        "final_text": _get_attr(item, "finaltext", "final_text"),
        "confidence": _to_float(_get_attr(item, "confidence")),
        "processed": bool(_get_attr(item, "processed", default=False)),
        "editedmanually": bool(_get_attr(item, "editedmanually", "edited_manually", default=False)),
        "edited_manually": bool(_get_attr(item, "editedmanually", "edited_manually", default=False)),
    }


def build_snapshot(
    inspection: Inspection,
    draft: ReportDraft,
    fields: list[Any],
    evidences: list[dict[str, Any]],
    transcriptions: list[Any],
    fixed_evidence_sections: list[dict[str, Any]],
) -> dict[str, Any]:
    inspection_id = _get_attr(inspection, "id")
    return {
        "draftid": _get_attr(draft, "id"),
        "draft_id": _get_attr(draft, "id"),
        "inspectionid": inspection_id,
        "inspection_id": inspection_id,
        "code": _get_attr(inspection, "code"),
        "clientname": _get_attr(inspection, "clientname", "client_name"),
        "equipmenttype": _get_attr(inspection, "equipmenttype", "equipment_type"),
        "inspectiontype": _get_attr(inspection, "inspectiontype", "inspection_type"),
        "inspectiondate": format_date(_get_attr(inspection, "inspectiondate", "inspection_date")),
        "location": _get_attr(inspection, "location"),
        "requestedby": _get_attr(inspection, "requestedby", "requested_by"),
        "responsibleinspector": _get_attr(inspection, "responsibleinspector", "responsible_inspector"),
        "status": _get_attr(inspection, "status"),
        "fields": [serialize_field(field) for field in fields],
        "evidences": evidences,
        "transcriptions": [serialize_transcription(item) for item in transcriptions],
        "fixedevidencesections": fixed_evidence_sections,
        "fixed_evidence_sections": fixed_evidence_sections,
    }


def infer_general_condition(field_map: dict[str, str], fields: list[Any]) -> str:
    explicit = find_field(
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
        normalized = normalize_key(explicit)
        if normalized in {"aceptado", "aprobado", "conforme", "ok"}:
            return "ACEPTADO"
        if normalized in {"rechazado"}:
            return "RECHAZADO"
        if normalized in {"observado"}:
            return "OBSERVADO"
        return explicit.upper()

    issue_count = sum(1 for field in fields or [] if has_issue_text(field_best_value(field, default="")))
    mismatch_count = sum(
        1
        for field in fields or []
        if safe_text(_get_attr(field, "validationstatus", "validation_status"), "pending").lower() in {"mismatch", "mismatched"}
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

    inspection_id = _get_attr(draft, "inspectionid", "inspection_id")
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

    transcription_query = db.query(Transcription)
    transcription_inspection_column = getattr(Transcription, "inspectionid", None)
    if transcription_inspection_column is None:
        transcription_inspection_column = getattr(Transcription, "inspection_id", None)
    if transcription_inspection_column is not None:
        transcription_query = transcription_query.filter(transcription_inspection_column == inspection.id)

    transcriptions = transcription_query.order_by(Transcription.id.asc()).all()

    fields = list(getattr(inspection, "fields", []) or [])
    evidences_raw = list(getattr(inspection, "evidences", []) or [])
    field_map = get_field_map(inspection)
    full_text = draft_text(draft)

    extracted_summary = extract_section(full_text, ["1. RESUMEN EJECUTIVO"], "")
    extracted_objective = extract_section(full_text, ["2. OBJETIVO"], "")
    extracted_scope = extract_section(full_text, ["3. ALCANCE"], "")
    extracted_protocol = extract_section(full_text, ["4. PROTOCOLO EMPLEADO"], "")
    extracted_frequency = extract_section(full_text, ["5. FRECUENCIA DE INSPECCIÓN"], "")
    extracted_standards = extract_section(full_text, ["6. NORMAS Y CÓDIGOS DE REFERENCIA", "6. NORMAS Y CODIGOS DE REFERENCIA"], "")
    extracted_equipment = extract_section(full_text, ["7. EQUIPOS DE INSPECCIÓN EMPLEADOS", "7. EQUIPOS DE INSPECCIÓN EMPELADOS"], "")
    extracted_criteria = extract_section(full_text, ["8. CRITERIOS DE INSPECCIÓN"], "")
    extracted_findings = extract_section(
        full_text,
        [
            "9. RESULTADOS DE LA INSPECCIÓN",
            "3. HALLAZGOS PRINCIPALES",
            "2. IDENTIFICACIÓN DE CAMPOS CRÍTICOS",
            "3. DATOS CAPTURADOS EN INSPECCIÓN",
        ],
        "",
    )
    extracted_ocr = extract_section(full_text, ["4. VALIDACIÓN OCR", "5. VALIDACIÓN OCR"], "")
    extracted_voice = extract_section(full_text, ["5. OBSERVACIONES TRANSCRITAS", "6. OBSERVACIONES TRANSCRITAS"], "")
    extracted_recommendations = extract_section(full_text, ["6. RECOMENDACIONES"], "")
    extracted_conclusion = extract_section(full_text, ["10. CONCLUSIONES", "7. INFORME REDACTADO", "7. CONCLUSIÓN PRELIMINAR"], "")

    plate = find_field(field_map, ["placa", "plate", "license_plate", "numero_placa"])
    vin = find_field(field_map, ["vin", "n_vin", "numero_vin", "no_vin"])
    brand = find_field(field_map, ["marca", "brand"])
    year = find_field(field_map, ["anio_fabricacion", "año_fabricacion", "year", "manufacture_year"])
    mileage = find_field(field_map, ["kilometraje", "mileage", "odometro", "odómetro"])
    age = find_field(field_map, ["antiguedad", "antigüedad", "age"])
    axles = find_field(field_map, ["numero_ejes", "n_ejes", "ejes", "axles"])
    payload = find_field(field_map, ["carga_util", "payload", "carga"])
    net_weight = find_field(field_map, ["peso_neto", "net_weight", "tara"])
    king_pin_brand = find_field(field_map, ["marca_king_pin", "king_pin_brand"])
    king_pin_model = find_field(field_map, ["modelo_king_pin", "king_pin_model"])
    king_pin_serial = find_field(field_map, ["serie_king_pin", "serial_king_pin", "king_pin_serial"])
    model_display = (
        plate
        if plate != "No registrado"
        else find_field(field_map, ["modelo", "model"], default=safe_text(_get_attr(inspection, "code")))
    )

    methods = build_methods(evidences_raw, transcriptions, full_text)
    general_condition = infer_general_condition(field_map, fields)
    evidences_payload = build_evidences(inspection, transcriptions)
    fixed_evidence_sections = build_fixed_evidence_sections(evidences_raw)
    fields_payload = [serialize_field(field) for field in fields]
    transcription_payload = [serialize_transcription(item) for item in transcriptions]

    findings = extracted_findings or build_findings_from_fields(fields)
    ocr_summary = extracted_ocr or build_ocr_summary_from_fields(fields)
    voice_summary = extracted_voice or build_voice_summary_from_transcriptions(transcriptions)
    recommendations = extracted_recommendations or build_recommendations_from_fields(fields, evidences_raw, transcriptions)
    conclusion = extracted_conclusion or build_conclusion_from_state(
        inspection=inspection,
        plate=plate,
        fields=fields,
        evidences=evidences_raw,
        transcriptions=transcriptions,
        general_condition=general_condition,
    )

    requested_by = safe_text(
        _get_attr(inspection, "requestedby", "requested_by"),
        safe_text(_get_attr(inspection, "clientname", "client_name")),
    )
    location = safe_text(_get_attr(inspection, "location"), "No registrada")
    inspection_date = _get_attr(inspection, "inspectiondate", "inspection_date")
    inspection_date_text = format_date(inspection_date)
    inspection_date_long = format_date_long(inspection_date)

    objective = build_objective(inspection, extracted_objective or extracted_summary)
    intro_paragraph = build_intro_paragraph(inspection=inspection, plate=plate, methods=methods)
    frequency_rows = build_frequency_rows(inspection)
    frequency_note = build_frequency_note(inspection, field_map, extracted_frequency)
    standards = build_standards(extracted_standards)
    inspection_equipment = build_inspection_equipment(evidences_raw, transcriptions, extracted_equipment)
    criteria = build_criteria(extracted_criteria)
    results = build_results_rows(inspection, fields, general_condition)

    equipment_type = safe_text(_get_attr(inspection, "equipmenttype", "equipment_type"))
    plate_display = safe_text(field_map.get("placa"), "Placa No Registrada")
    equipment_display = f"{equipment_type.upper()}: {plate_display}"
    report_code_display = build_report_code_display(inspection, field_map)

    summary = extracted_summary or objective
    snapshot = build_snapshot(
        inspection=inspection,
        draft=draft,
        fields=fields,
        evidences=evidences_payload,
        transcriptions=transcriptions,
        fixed_evidence_sections=fixed_evidence_sections,
    )

    branding = {
        "logo_path": COMPANY_INFO["logo_path"],
        "logopath": COMPANY_INFO["logo_path"],
        "report_title": "INFORME FINAL",
        "reporttitle": "INFORME FINAL",
        "report_code_display": report_code_display,
        "reportcodedisplay": report_code_display,
        "report_subtitle": "ENSAYOS NO DESTRUCTIVOS (END)",
        "reportsubtitle": "ENSAYOS NO DESTRUCTIVOS (END)",
        "equipment_display": equipment_display,
        "equipmentdisplay": equipment_display,
        "divider_lines": True,
        "dividerlines": True,
    }

    header = {
        "report_title": "INFORME FINAL",
        "reporttitle": "INFORME FINAL",
        "report_code": safe_text(_get_attr(inspection, "code")),
        "reportcode": safe_text(_get_attr(inspection, "code")),
        "report_code_display": report_code_display,
        "reportcodedisplay": report_code_display,
        "report_subtitle": "ENSAYOS NO DESTRUCTIVOS (END)",
        "reportsubtitle": "ENSAYOS NO DESTRUCTIVOS (END)",
        "equipment_display": equipment_display,
        "equipmentdisplay": equipment_display,
        "inspection_type": safe_text(_get_attr(inspection, "inspectiontype", "inspection_type"), "No registrado").upper(),
        "inspectiontype": safe_text(_get_attr(inspection, "inspectiontype", "inspection_type"), "No registrado").upper(),
        "inspection_date": inspection_date_text,
        "inspectiondate": inspection_date_text,
        "inspection_date_long": inspection_date_long,
        "inspectiondatelong": inspection_date_long,
        "methods": methods,
        "methods_display": " / ".join(methods),
        "methodsdisplay": " / ".join(methods),
        "general_condition": general_condition,
        "generalcondition": general_condition,
        "location": location.upper(),
        "logo_path": COMPANY_INFO["logo_path"],
        "logopath": COMPANY_INFO["logo_path"],
    }

    technical_info = {
        "requested_by": requested_by,
        "requestedby": requested_by,
        "address": find_field(field_map, ["direccion", "address", "direccion_cliente"], location),
        "service_responsible": safe_text(_get_attr(inspection, "responsibleinspector", "responsible_inspector"), "Inspector no registrado"),
        "serviceresponsible": safe_text(_get_attr(inspection, "responsibleinspector", "responsible_inspector"), "Inspector no registrado"),
        "inspection_date_text": inspection_date_text,
        "inspectiondatetext": inspection_date_text,
        "inspection_date_long": inspection_date_long,
        "inspectiondatelong": inspection_date_long,
        "intro_paragraph": intro_paragraph,
        "introparagraph": intro_paragraph,
        "signature_path": "app/static/reports/signatures/firma_responsable.png",
    }

    identification = {
        "tipo_equipo": equipment_type,
        "tipoequipo": equipment_type,
        "placa": plate,
        "marca": brand,
        "vin": vin,
        "anio_fabricacion": year,
        "aniofabricacion": year,
        "kilometraje": mileage,
        "antiguedad": age,
        "numero_ejes": axles,
        "numeroejes": axles,
        "carga_util": payload,
        "cargautil": payload,
        "peso_neto": net_weight,
        "pesoneto": net_weight,
        "marca_king_pin": king_pin_brand,
        "marcakingpin": king_pin_brand,
        "modelo_king_pin": king_pin_model,
        "modelokingpin": king_pin_model,
        "serie_king_pin": king_pin_serial,
        "seriekingpin": king_pin_serial,
    }

    footer = {
        "company_line": f"{COMPANY_INFO['name']} RUC: {COMPANY_INFO['ruc']}",
        "companyline": f"{COMPANY_INFO['name']} RUC: {COMPANY_INFO['ruc']}",
        "address_line": COMPANY_INFO["address"],
        "addressline": COMPANY_INFO["address"],
        "contact_line": f"{COMPANY_INFO['phones']} | {COMPANY_INFO['email']}",
        "contactline": f"{COMPANY_INFO['phones']} | {COMPANY_INFO['email']}",
        "website_line": COMPANY_INFO["website"],
        "websiteline": COMPANY_INFO["website"],
        "page_number_template": "{page_number} de {page_count}",
        "pagenumbertemplate": "{page_number} de {page_count}",
    }

    document_meta = {
        "show_footer": True,
        "showfooter": True,
        "show_dividers": True,
        "showdividers": True,
        "show_cover_logo": True,
        "showcoverlogo": True,
        "render_results_table": True,
        "renderresultstable": True,
        "render_evidence_gallery": True,
        "renderevidencegallery": True,
    }

    context = {
        "draft": draft,
        "inspection": inspection,
        "company": COMPANY_INFO,
        "branding": branding,
        "header": header,
        "technical_info": technical_info,
        "technicalinfo": technical_info,
        "identification": identification,
        "summary": summary,
        "objective": objective,
        "scope": extracted_scope.splitlines() if extracted_scope else build_scope(inspection, methods, evidences_raw, transcriptions),
        "protocol": build_protocol(inspection, extracted_protocol),
        "frequency": frequency_note,
        "frequency_table": frequency_rows,
        "frequencytable": frequency_rows,
        "standards": standards,
        "inspection_equipment": inspection_equipment,
        "inspectionequipment": inspection_equipment,
        "inspection_equipment_table": inspection_equipment,
        "inspectionequipmenttable": inspection_equipment,
        "criteria": criteria,
        "results": results,
        "conclusion": conclusion,
        "ocr_summary": ocr_summary,
        "ocrsummary": ocr_summary,
        "voice_summary": voice_summary,
        "voicesummary": voice_summary,
        "recommendations": recommendations,
        "evidences": evidences_payload,
        "findings": findings,
        "fields": fields_payload,
        "transcriptions": transcription_payload,
        "fixed_evidence_sections": fixed_evidence_sections,
        "fixedevidencesections": fixed_evidence_sections,
        "snapshot": snapshot,
        "footer": footer,
        "document_meta": document_meta,
        "documentmeta": document_meta,
    }

    return context

def buildcompanyreportcontext(db: Session, draftid: int) -> dict[str, Any]:
    return build_company_report_context(db, draftid)

def buildfixedevidencesections(evidences: list[Any]) -> list[dict[str, Any]]:
    return build_fixed_evidence_sections(evidences)

def buildevidencesectionbyslots(evidences: list[Any]) -> str:
    return build_evidence_section_by_slots(evidences)