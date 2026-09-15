import hashlib
import mimetypes
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from docx import Document as load_document
from docx.document import Document as docx_document_type
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.schemas.imports import (
    docx_import_preview_response,
    imported_image_preview,
    parsed_result_row,
)


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    value = value.replace("\xa0", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _normalize_text(value: str | None) -> str:
    value = _clean_text(value).lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return value

def _normalize_inline_value(value: str | None) -> str | None:
    if value is None:
        return None

    cleaned = _clean_text(value)
    if not cleaned:
        return None

    cleaned = re.sub(r"\s*\|\s*", " | ", cleaned)
    cleaned = re.sub(r"\s+([,;:.])", r"\1", cleaned)
    cleaned = re.sub(r"\.{2,}", ".", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)

    return cleaned.strip()


def _normalize_person_name(value: str | None) -> str | None:
    cleaned = _normalize_inline_value(value)
    if not cleaned:
        return None

    cleaned = re.sub(r"\.+$", "", cleaned)
    return cleaned.strip()


def _normalize_observation_value(value: str | None) -> str | None:
    cleaned = _normalize_inline_value(value)
    if not cleaned:
        return None

    if cleaned in {"-", "--", "---", "----", "-----"}:
        return "----"

    return cleaned


def _iter_block_items(document: docx_document_type):
    parent = document.element.body
    for child in parent.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, document)
        elif isinstance(child, CT_Tbl):
            yield Table(child, document)


def _table_to_lines(table: Table) -> list[str]:
    lines: list[str] = []
    for row in table.rows:
        cells = [_clean_text(cell.text) for cell in row.cells]
        cells = [cell for cell in cells if cell]
        if cells:
            lines.append(" | ".join(cells))
    return lines


def _document_to_lines(document: docx_document_type) -> list[str]:
    lines: list[str] = []
    for block in _iter_block_items(document):
        if isinstance(block, Paragraph):
            text = _clean_text(block.text)
            if text:
                lines.append(text)
        elif isinstance(block, Table):
            lines.extend(_table_to_lines(block))
    return lines


def _extract_section(text: str, start_markers: list[str], end_markers: list[str]) -> str:
    lower_text = text.lower()
    start_index = -1
    end_index = len(text)

    for marker in start_markers:
        idx = lower_text.find(marker.lower())
        if idx != -1:
            start_index = idx
            break

    if start_index == -1:
        return ""

    for marker in end_markers:
        idx = lower_text.find(marker.lower(), start_index + 1)
        if idx != -1:
            end_index = min(end_index, idx)

    return _clean_text(text[start_index:end_index])


def _find_first(patterns: list[str], text: str) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            return _clean_text(match.group(1))
    return None


def _parse_date_string(value: str | None) -> str | None:
    if not value:
        return None

    raw = _clean_text(value)

    for fmt in ("%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue

    normalized = _normalize_text(raw)
    match = re.search(r"([0-9]{1,2})\s+de\s+([a-z]+)\s+(?:del\s+)?([0-9]{4})", normalized)
    if not match:
        return raw

    day = int(match.group(1))
    month_name = match.group(2)
    year = int(match.group(3))

    month_map = {
        "enero": 1,
        "febrero": 2,
        "marzo": 3,
        "abril": 4,
        "mayo": 5,
        "junio": 6,
        "julio": 7,
        "agosto": 8,
        "septiembre": 9,
        "setiembre": 9,
        "octubre": 10,
        "noviembre": 11,
        "diciembre": 12,
    }

    month = month_map.get(month_name)
    if not month:
        return raw

    try:
        return datetime(year, month, day).date().isoformat()
    except ValueError:
        return raw


def _extract_basic_fields(full_text: str, source_filename: str) -> dict[str, str | None]:
    report_code = _find_first(
        [
            r"\b(GS\s*[-–—]{1,2}\s*.*?SR\s*-\s*[A-Z]+)\b",
        ],
        full_text,
    )

    plate = _normalize_inline_value(
        _find_first(
            [
                r"SEMIRREMOLQUE\s*:\s*([A-Z0-9-]+)",
                r"N[°º]?\s*De placa\s*:?\s*([A-Z0-9-]+)",
                r"De placa\s*:?\s*([A-Z0-9-]+)",
                r"placa\s*:?\s*([A-Z0-9-]+)",
            ],
            full_text,
        )
    )

    client_name = _normalize_inline_value(
        _find_first(
            [
                r"SOLICITADO POR\s*:?\s*(.+?)(?=\s+RESPONSABLE DEL SERVICIO\s*:)",
                r"Ha solicitud de la empresa\s+(.+?)(?=,\s+Se ha realizado la inspección)",
            ],
            full_text,
        )
    )

    inspector_name = _normalize_person_name(
        _find_first(
            [
                r"RESPONSABLE DEL SERVICIO\s*:?\s*(.+?)(?=\s+FECHA DE INSPECCI[ÓO]N\s*:)",
            ],
            full_text,
        )
    )

    inspection_date = _parse_date_string(
        _find_first(
            [
                r"FECHA DE INSPECCI[ÓO]N\s*:?\s*([0-9]{1,2}\s+de\s+[A-Za-zÁÉÍÓÚáéíóú]+\s+(?:del\s+)?[0-9]{4})",
                r"FECHA DE INSPECCI[ÓO]N\s*:?\s*([0-9]{2}/[0-9]{2}/[0-9]{4})",
                r"FECHA DE INSPECCI[ÓO]N\s*:?\s*([0-9]{2}-[0-9]{2}-[0-9]{4})",
            ],
            full_text,
        )
    )

    fields = {
        "source_filename": source_filename,
        "report_code": report_code,
        "plate": plate,
        "client_name": client_name,
        "inspector_name": inspector_name,
        "inspection_date": inspection_date,
        "equipment_type": _normalize_inline_value(
            _find_first(
                [
                    r"Tipo de Equipo\s*:?\s*(.+?)(?=\s+N[º°#№]?\s*De placa)",
                    r"Tipo de Equipo\s*:?\s*(.+?)(?=\s+Marca\s*:)",
                    r"Tipo de Equipo\s*:?\s*(.+?)(?=\s+N[°º#№]?\s*de Vin)",
                ],
                full_text,
            )
        ),
        "brand": _find_first(
            [
                r"Marca\s*:?\s*(.+?)(?=\s+N[°º#№]?\s*de Vin)",
            ],
            full_text,
        ),
        "vin": _find_first(
            [
                r"N[°º#№]?\s*de Vin\s*:?\s*([A-Z0-9\-]+)",
            ],
            full_text,
        ),
        "manufacturing_year": _find_first(
            [
                r"Año de fabricación\s*:?\s*([0-9]{4})",
            ],
            full_text,
        ),
        "reference_mileage": _find_first(
            [
                r"Kilometraje de Referencia\s*:?\s*([0-9][0-9\.,]*)",
            ],
            full_text,
        ),
        "antiquity_years": _find_first(
            [
                r"Antigüedad\s*:?\s*([0-9]+)",
            ],
            full_text,
        ),
        "axle_count": _find_first(
            [
                r"N[º°#№]?\s*de Ejes\s*:?\s*([0-9]{1,2})",
            ],
            full_text,
        ),
        "payload_kg": _find_first(
            [
                r"Carga Útil\s*:?\s*([0-9]+(?:\.[0-9]+)?)\s*Kg",
            ],
            full_text,
        ),
        "net_weight_kg": _find_first(
            [
                r"Peso Neto\s*:?\s*([0-9]+(?:\.[0-9]+)?)\s*Kg",
            ],
            full_text,
        ),
        "king_pin_brand": _find_first(
            [
                r"Marca de King pin\s*:?\s*(.+?)(?=\s+Modelo de King Pin)",
            ],
            full_text,
        ),
    }

    return fields


def _extract_results(full_text: str) -> list[parsed_result_row]:
    results_section = _extract_section(
        full_text,
        [
            "RESULTADOS DE LA INSPECCIÓN",
            "RESULTADOS DE LA INSPECCION",
            "9. RESULTADOS DE LA INSPECCIÓN",
            "9. RESULTADOS DE LA INSPECCION",
        ],
        [
            "CONCLUSIONES",
            "10. CONCLUSIONES",
        ],
    )

    searchable_text = results_section or full_text

    components = [
        "Chasis",
        "Puntas de Ejes",
        "Balancines",
        "Soporte de muelles",
        "Hojas de muelles/bolsas de Aire",
        "Plancha de King pin",
        "King Pin",
    ]

    rows: list[parsed_result_row] = []

    for component in components:
        pattern = (
            rf"(?:Semirremolque|King Pin)\s*\|\s*{re.escape(component)}\s*"
            rf"\|\s*(Aceptado|Rechazado)\s*"
            rf"\|\s*([^|]*?)\s*"
            rf"\|\s*([^|]*?)"
            rf"(?=\s+(?:Semirremolque|King Pin)\s*\||\s+CONCLUSIONES\b)"
        )

        match = re.search(pattern, searchable_text, re.IGNORECASE | re.DOTALL)
        if match:
            rows.append(
                parsed_result_row(
                    component=component,
                    condition=_normalize_inline_value(match.group(1)),
                    observations=_normalize_observation_value(match.group(2)),
                    action_required=_normalize_observation_value(match.group(3)),
                )
            )
            continue

        fallback_pattern = (
            rf"{re.escape(component)}\s*\|\s*(Aceptado|Rechazado)\s*"
            rf"\|\s*([^|]*?)\s*\|\s*([^|]*?)"
            rf"(?=\s+[A-ZÁÉÍÓÚA-Za-z/ ]+\s*\||\s+CONCLUSIONES\b)"
        )

        fallback_match = re.search(fallback_pattern, searchable_text, re.IGNORECASE | re.DOTALL)
        if fallback_match:
            rows.append(
                parsed_result_row(
                    component=component,
                    condition=_normalize_inline_value(fallback_match.group(1)),
                    observations=_normalize_observation_value(fallback_match.group(2)),
                    action_required=_normalize_observation_value(fallback_match.group(3)),
                )
            )

    return rows


def _extract_media_images_from_zip(file_path: str | Path) -> list[dict[str, Any]]:
    media: list[dict[str, Any]] = []

    with ZipFile(file_path, "r") as archive:
        media_names = [
            name
            for name in archive.namelist()
            if name.startswith("word/media/")
        ]

        for sequence, name in enumerate(media_names, start=1):
            filename = Path(name).name
            blob = archive.read(name)
            content_type = mimetypes.guess_type(filename)[0]
            sha1 = hashlib.sha1(blob).hexdigest()

            media.append(
                {
                    "sequence": sequence,
                    "filename": filename,
                    "content_type": content_type,
                    "size_bytes": len(blob),
                    "sha1": sha1,
                    "extension": Path(filename).suffix.lower(),
                    "blob": blob,
                    "caption": None,
                }
            )

    return media


def _extract_conclusion(full_text: str) -> str | None:
    section = _extract_section(
        full_text,
        ["10. CONCLUSIONES"],
        ["RESULTADOS", "INSPECCIÓN VISUAL", "INSPECCION VISUAL"],
    )
    conclusion = _find_first(
        [
            r"CONCLUSIONES\s*(.+)",
            r"El equipo.*",
        ],
        section or full_text,
    )
    if conclusion:
        return conclusion

    lines = [_clean_text(line) for line in section.splitlines() if _clean_text(line)]
    if lines:
        return " ".join(lines[:3])
    return None


def _extract_photo_captions(lines: list[str]) -> list[str]:
    captions: list[str] = []
    for line in lines:
        normalized = _normalize_text(line)
        if normalized.startswith("foto ") or normalized.startswith("fotos "):
            captions.append(_clean_text(line))
            continue
        if "muestra ejes inspeccionados" in normalized:
            captions.append(_clean_text(line))
            continue
        if "king pin y plancha king pin" in normalized:
            captions.append(_clean_text(line))
    return captions


def _extract_inline_images(document: docx_document_type) -> list[dict[str, Any]]:
    images: list[dict[str, Any]] = []

    for sequence, shape in enumerate(document.inline_shapes, start=1):
        blips = shape._inline.xpath(".//*[local-name()='blip']")
        if not blips:
            continue

        rid = None
        for key, value in blips[0].attrib.items():
            if key.endswith("embed"):
                rid = value
                break

        if not rid:
            continue

        image_part = document.part.related_parts.get(rid)
        if image_part is None:
            continue

        filename = Path(str(image_part.partname)).name
        content_type = getattr(image_part, "content_type", None) or mimetypes.guess_type(filename)[0]
        blob = image_part.blob
        sha1 = hashlib.sha1(blob).hexdigest()

        images.append(
            {
                "sequence": sequence,
                "filename": filename,
                "content_type": content_type,
                "size_bytes": len(blob),
                "sha1": sha1,
                "extension": Path(filename).suffix.lower(),
                "blob": blob,
                "caption": None,
            }
        )

    return images


def _attach_captions(images: list[dict[str, Any]], captions: list[str]) -> None:
    if not images or not captions:
        return

    candidate_indexes = [
        index
        for index, image in enumerate(images)
        if image["extension"] in {".jpg", ".jpeg", ".png"} and image["size_bytes"] >= 40_000
    ]

    if not candidate_indexes:
        return

    start_index = max(0, len(candidate_indexes) - len(captions))
    target_indexes = candidate_indexes[start_index : start_index + len(captions)]

    for index, caption in zip(target_indexes, captions):
        images[index]["caption"] = caption


def _extract_axle_number(caption: str | None) -> int | None:
    if not caption:
        return None
    match = re.search(r"eje\s*([0-9]+)", _normalize_text(caption))
    if match:
        return int(match.group(1))
    return None


def _extract_side(caption: str | None) -> str | None:
    normalized = _normalize_text(caption)
    if "izquierdo" in normalized or "izquierda" in normalized:
        return "izquierdo"
    if "derecho" in normalized or "derecha" in normalized:
        return "derecho"
    return None


def _detect_component_code(caption: str | None) -> str | None:
    normalized = _normalize_text(caption)
    if "king pin" in normalized and "plancha" in normalized:
        return "king_pin_plancha"
    if "king pin" in normalized:
        return "king_pin"
    if "munon" in normalized or "muñon" in normalized:
        return "munon"
    if "ejes inspeccionados" in normalized or "eje" in normalized:
        return "eje"
    if "chasis" in normalized or "plataforma" in normalized:
        return "chasis"
    return None


def _detect_evidence_slot(caption: str | None) -> str | None:
    normalized = _normalize_text(caption)
    if "king pin y plancha king pin" in normalized:
        return "king_pin_plancha"
    if "munon" in normalized or "muñon" in normalized:
        return "munon"
    if "ejes inspeccionados" in normalized:
        return "ejes_vista_general"
    if "lado izquierdo" in normalized:
        return "lado_izquierdo"
    if "lado derecho" in normalized:
        return "lado_derecho"
    if "chasis" in normalized or "plataforma" in normalized:
        return "chasis"
    return None


def _classify_images(images: list[dict[str, Any]]) -> list[imported_image_preview]:
    response: list[imported_image_preview] = []

    for image in images:
        caption = _clean_text(image.get("caption"))
        normalized_caption = _normalize_text(caption)
        classification = "review"
        reason = "sin_regla_fuerte"
        evidence_slot = None

        if image["extension"] in {".tif", ".tiff"}:
            classification = "discard"
            reason = "grafico_o_referencia_no_fotografica"
        elif image["size_bytes"] < 35_000 and image["sequence"] <= 8:
            classification = "discard"
            reason = "encabezado_logo_qr_o_firma"
        elif image["sequence"] <= 6 and not caption:
            classification = "discard"
            reason = "portada_o_elemento_de_encabezado"
        elif "foto " in normalized_caption or "muestra ejes inspeccionados" in normalized_caption:
            classification = "evidence"
            reason = "caption_fotografico_detectado"
            evidence_slot = _detect_evidence_slot(caption)
        elif any(token in normalized_caption for token in ["king pin", "munon", "muñon", "eje", "chasis"]):
            classification = "evidence"
            reason = "caption_tecnico_detectado"
            evidence_slot = _detect_evidence_slot(caption)
        elif image["sequence"] > 8 and image["extension"] in {".jpg", ".jpeg", ".png"} and image["size_bytes"] >= 80_000:
            classification = "review"
            reason = "imagen_posterior_sin_caption_claro"

        response.append(
            imported_image_preview(
                sequence=image["sequence"],
                filename=image["filename"],
                content_type=image["content_type"],
                size_bytes=image["size_bytes"],
                sha1=image["sha1"],
                caption=caption or None,
                classification=classification,
                evidence_slot=evidence_slot,
                component_code=_detect_component_code(caption),
                side=_extract_side(caption),
                axle_number=_extract_axle_number(caption),
                reason=reason,
                metadata_json={
                    "extension": image["extension"],
                },
            )
        )

    return response


def build_synthetic_transcription(
    extracted_fields: dict[str, str | None],
    results: list[parsed_result_row],
    conclusion: str | None,
) -> str:
    plate = _normalize_inline_value(extracted_fields.get("plate")) or "equipo sin placa detectada"
    inspector = _normalize_person_name(extracted_fields.get("inspector_name")) or "inspector no identificado"

    lines = [
        f"Informe histórico importado del equipo {plate}.",
        f"Inspector responsable detectado: {inspector}.",
    ]

    if results:
        for row in results:
            if row.condition:
                lines.append(
                    f"Componente {row.component}: condición {_normalize_inline_value(row.condition)}."
                )

    normalized_conclusion = _normalize_inline_value(conclusion)
    if normalized_conclusion:
        lines.append(f"Conclusión original del informe: {normalized_conclusion}")

    return " ".join(lines)


def build_base_draft(
    extracted_fields: dict[str, str | None],
    results: list[parsed_result_row],
    conclusion: str | None,
) -> str:
    lines = [
        "INFORME TÉCNICO IMPORTADO",
        "",
        f"Código de informe: {_normalize_inline_value(extracted_fields.get('report_code')) or '--'}",
        f"Placa: {_normalize_inline_value(extracted_fields.get('plate')) or '--'}",
        f"Cliente: {_normalize_inline_value(extracted_fields.get('client_name')) or '--'}",
        f"Inspector responsable: {_normalize_person_name(extracted_fields.get('inspector_name')) or '--'}",
        f"Fecha de inspección: {_normalize_inline_value(extracted_fields.get('inspection_date')) or '--'}",
        f"Tipo de equipo: {_normalize_inline_value(extracted_fields.get('equipment_type')) or '--'}",
        f"Marca: {_normalize_inline_value(extracted_fields.get('brand')) or '--'}",
        f"VIN: {_normalize_inline_value(extracted_fields.get('vin')) or '--'}",
        f"Año de fabricación: {_normalize_inline_value(extracted_fields.get('manufacturing_year')) or '--'}",
        "",
        "RESULTADOS IMPORTADOS",
    ]

    if results:
        for row in results:
            lines.append(
                f"- {row.component}: {_normalize_inline_value(row.condition) or '--'} | "
                f"observaciones: {_normalize_observation_value(row.observations) or '--'} | "
                f"acción: {_normalize_observation_value(row.action_required) or '--'}"
            )
    else:
        lines.append("- No se detectaron resultados estructurados.")

    lines.extend(
        [
            "",
            "CONCLUSIÓN",
            _normalize_inline_value(conclusion) or "No se detectó conclusión original.",
        ]
    )

    return "\n".join(lines)


def preview_docx_report(file_path: str | Path) -> docx_import_preview_response:
    path = Path(file_path)
    document = load_document(path)
    lines = _document_to_lines(document)
    full_text = "\n".join(lines)

    extracted_fields = _extract_basic_fields(full_text, path.name)
    results = _extract_results(full_text)
    conclusion = _extract_conclusion(full_text)

    raw_images = _extract_inline_images(document)
    if not raw_images:
        raw_images = _extract_media_images_from_zip(path)

    captions = _extract_photo_captions(lines)
    _attach_captions(raw_images, captions)
    images = _classify_images(raw_images)

    synthetic_transcription = build_synthetic_transcription(extracted_fields, results, conclusion)
    draft_base = build_base_draft(extracted_fields, results, conclusion)

    warnings: list[str] = []
    required_keys = ["plate", "client_name", "inspection_date"]
    for key in required_keys:
        if not extracted_fields.get(key):
            warnings.append(f"no_se_detecto_{key}")

    evidence_count = len([image for image in images if image.classification == "evidence"])
    if evidence_count == 0:
        warnings.append("no_se_detectaron_evidencias_con_regla_fuerte")

    if len(images) == 0:
        warnings.append("el_documento_no_contiene_imagenes_inline")

    return docx_import_preview_response(
        source_filename=path.name,
        report_code=extracted_fields.get("report_code"),
        extracted_fields=extracted_fields,
        results=results,
        images=images,
        conclusion=conclusion,
        synthetic_transcription=synthetic_transcription,
        draft_base=draft_base,
        warnings=warnings,
    )


def extract_evidence_binaries(file_path: str | Path) -> dict[str, bytes]:
    path = Path(file_path)
    document = load_document(path)
    images = _extract_inline_images(document)
    return {image["filename"]: image["blob"] for image in images}


def extract_zip_media(file_path: str | Path) -> dict[str, bytes]:
    media: dict[str, bytes] = {}
    with ZipFile(file_path, "r") as archive:
        for name in archive.namelist():
            if name.startswith("word/media/"):
                media[Path(name).name] = archive.read(name)
    return media