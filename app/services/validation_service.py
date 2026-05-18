import re
import unicodedata
from difflib import SequenceMatcher

from sqlalchemy.orm import Session, selectinload

from app.db.models import Inspection
from app.domain.rules.numeric_rules import compare_numeric, find_numeric_value
from app.domain.rules.plate_rules import compare_plate, find_plate
from app.domain.rules.serial_rules import compare_serial, find_serial
from app.domain.rules.vin_rules import compare_vin, find_vin
from app.services.ocr_service import extract_text_from_evidence_record

NUMERIC_TYPES = {"number", "numeric", "integer", "float", "decimal"}

LABEL_HINTS = [
    "EMPRESA", "FABRICANTE", "ESPECIALIDAD", "MARCA", "PAIS", "ORIGEN", "ANIO", "AÑO",
    "SERIE", "EJES", "CARROCERIA", "MODELO", "PESO", "CARGA", "VIN", "PLACA",
    "DOM", "PLANTA", "TELEF",
]


def _strip_accents(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _normalize_generic(value: str | None) -> str:
    if not value:
        return ""
    value = _strip_accents(value).upper().strip()
    return re.sub(r"[^A-Z0-9]+", "", value)


def _normalize_soft(value: str | None) -> str:
    if not value:
        return ""
    value = _strip_accents(value).upper().strip()
    return re.sub(r"\s+", " ", value)


def _cleanup_candidate(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    value = re.sub(r"\s+", " ", value)
    value = value.strip(" .,:;|-")
    return value or None


def _similarity(left: str | None, right: str | None) -> float:
    a = _normalize_generic(left)
    b = _normalize_generic(right)
    if not a or not b:
        return 0.0
    return round(SequenceMatcher(None, a, b).ratio(), 4)


def _looks_like_label(line: str | None) -> bool:
    soft = _normalize_soft(line)
    if not soft:
        return False
    if ":" in soft and len(soft) <= 40:
        return True
    return any(token in soft for token in LABEL_HINTS) and len(soft) <= 40


def _field_aliases(field_key: str, field_label: str | None) -> list[str]:
    joined_generic = _normalize_generic(f"{field_key} {field_label or ''}")
    aliases: list[str] = []

    def add(*values: str):
        for value in values:
            if value not in aliases:
                aliases.append(value)

    if any(token in joined_generic for token in ["EMPRESA", "FABRICANTE"]):
        add("EMPRESA", "FABRICANTE")

    if "ESPECIALIDAD" in joined_generic:
        add("ESPECIALIDAD")

    if "MARCA" in joined_generic:
        add("MARCA")

    if any(token in joined_generic for token in ["PAIS", "ORIGEN"]):
        add("PAIS DE ORIGEN", "PAIS", "PAIS DE FAB")

    if any(token in joined_generic for token in ["ANIO", "ANO", "AÑO"]):
        add("AÑO DE FAB.", "ANO DE FAB.", "ANIO DE FAB.", "AÑO", "ANIO")

    if any(token in joined_generic for token in ["SERIE", "SERIAL"]):
        add("N° DE SERIE", "NRO DE SERIE", "NUMERO DE SERIE", "DE SERIE", "SERIE")

    if "EJES" in joined_generic:
        add("N° DE EJES", "NRO DE EJES", "NUMERO DE EJES", "EJES")

    if "CARROCERIA" in joined_generic:
        add("CARROCERIA")

    if "MODELO" in joined_generic:
        add("MODELO")

    if "PESONETO" in joined_generic:
        add("PESO NETO")

    if "PESOBRUTO" in joined_generic:
        add("PESO BRUTO")

    if "CARGAUTIL" in joined_generic:
        add("CARGA UTIL", "CARGA ÚTIL")

    if "VIN" in joined_generic:
        add("VIN", "N° VIN", "NUMERO VIN")

    if "PLACA" in joined_generic or "PLATE" in joined_generic:
        add("PLACA")

    return aliases


def _extract_same_line_value(original_line: str, alias: str) -> str | None:
    cleaned = original_line.strip()
    if not cleaned:
        return None

    alias_soft = _normalize_soft(alias)
    line_soft = _normalize_soft(cleaned)

    if alias_soft not in line_soft:
        return None

    split_match = re.split(r"[:=\-]\s*", cleaned, maxsplit=1)
    if len(split_match) == 2:
        left, right = split_match
        if alias_soft in _normalize_soft(left):
            return _cleanup_candidate(right)

    pattern = re.compile(rf"{re.escape(alias)}\s+(.+)$", flags=re.IGNORECASE)
    match = pattern.search(cleaned)
    if match:
        return _cleanup_candidate(match.group(1))

    return None


def _numbers_from_text(text: str) -> list[str]:
    return re.findall(r"\b\d{1,6}\b", text or "")


def _serial_candidates(text: str) -> list[str]:
    return re.findall(r"\b[A-Z0-9]{8,25}\b", _normalize_soft(text))


def _find_value_near_alias(text: str, aliases: list[str], expected_type: str, manual_value: str | None) -> str | None:
    if not text or not aliases:
        return None

    lines = [line.strip() for line in text.splitlines() if line.strip()]

    for idx, line in enumerate(lines):
        line_soft = _normalize_soft(line)

        for alias in aliases:
            alias_soft = _normalize_soft(alias)
            if alias_soft not in line_soft:
                continue

            same_line_value = _extract_same_line_value(line, alias)
            if same_line_value:
                if expected_type.lower() in NUMERIC_TYPES:
                    return find_numeric_value(same_line_value, manual_value) or same_line_value
                return same_line_value

            for next_idx in range(idx + 1, min(idx + 4, len(lines))):
                candidate = _cleanup_candidate(lines[next_idx])
                if not candidate or _looks_like_label(candidate):
                    continue

                if expected_type.lower() in NUMERIC_TYPES:
                    return find_numeric_value(candidate, manual_value) or candidate

                return candidate

    return None


def _extract_year(source_text: str, full_text: str) -> str | None:
    match = re.search(r"\b20\d{2}\b", source_text) or re.search(r"\b20\d{2}\b", full_text)
    return match.group(0) if match else None


def _extract_ejes(source_text: str, full_text: str) -> str | None:
    for text in [source_text, full_text]:
        nums = _numbers_from_text(text)
        for num in nums:
            if 1 <= len(num) <= 2 and 1 <= int(num) <= 8:
                return num
    return None


def _extract_weight(source_text: str, full_text: str, manual_value: str | None) -> str | None:
    hinted = find_numeric_value(source_text, manual_value)
    if hinted and len(hinted) >= 3:
        return hinted

    for text in [source_text, full_text]:
        nums = _numbers_from_text(text)
        candidates = [n for n in nums if len(n) >= 3]
        if manual_value:
            target = re.sub(r"\D", "", manual_value)
            if target:
                for n in candidates:
                    if n == target:
                        return n
        if candidates:
            return max(candidates, key=len)

    return None


def _extract_model_or_text(near_value: str | None, manual_value: str | None, full_text: str) -> str | None:
    if near_value:
        return near_value

    if manual_value:
        for line in full_text.splitlines():
            candidate = _cleanup_candidate(line)
            if not candidate:
                continue
            if _similarity(candidate, manual_value) >= 0.72:
                return candidate

    return None


def _extract_series(source_text: str, full_text: str, manual_value: str | None) -> str | None:
    direct = find_serial(source_text, manual_value)
    if direct and len(re.sub(r"[^A-Z0-9]", "", direct)) >= 8:
        return direct

    candidates = _serial_candidates(source_text) + _serial_candidates(full_text)
    if manual_value:
        target = _normalize_generic(manual_value)
        ranked = sorted(candidates, key=lambda c: _similarity(c, target), reverse=True)
        if ranked and _similarity(ranked[0], target) >= 0.55:
            return ranked[0]

    for candidate in candidates:
        if len(candidate) >= 8 and not candidate.isdigit():
            return candidate

    return None


def _extract_candidate(
    field_key: str,
    field_label: str | None,
    expected_type: str,
    text: str,
    manual_value: str | None,
) -> str | None:
    key = (field_key or "").lower()
    expected = (expected_type or "").lower()

    aliases = _field_aliases(field_key, field_label)
    near_value = _find_value_near_alias(text, aliases, expected_type, manual_value)
    source_text = near_value or text

    if "vin" in key:
        return find_vin(source_text) or find_vin(text)

    if "plac" in key or "plate" in key:
        return find_plate(source_text) or find_plate(text)

    if "serial" in key or "serie" in key:
        return _extract_series(source_text, text, manual_value)

    if "ejes" in key:
        return _extract_ejes(source_text, text)

    if "pesoneto" in _normalize_generic(field_key) or "pesoneto" in _normalize_generic(field_label or ""):
        return _extract_weight(source_text, text, manual_value)

    if "pesobruto" in _normalize_generic(field_key) or "pesobruto" in _normalize_generic(field_label or ""):
        return _extract_weight(source_text, text, manual_value)

    if "cargautil" in _normalize_generic(field_key) or "cargautil" in _normalize_generic(field_label or ""):
        return _extract_weight(source_text, text, manual_value)

    if "anio" in key or "año" in key:
        return _extract_year(source_text, text)

    if expected in NUMERIC_TYPES:
        return find_numeric_value(source_text, manual_value) or find_numeric_value(text, manual_value) or near_value

    if near_value:
        return near_value

    return _extract_model_or_text(near_value, manual_value, text)


def _compare_values(field_key: str, expected_type: str, manual_value: str | None, ocr_value: str | None) -> tuple[str, str]:
    key = (field_key or "").lower()
    expected = (expected_type or "").lower()

    if not ocr_value:
        return "not_found", "No se detectó valor OCR para este campo"

    if "vin" in key:
        return (
            ("matched", "VIN coincide con OCR")
            if compare_vin(manual_value, ocr_value)
            else ("mismatch", "VIN no coincide con OCR")
        )

    if "plac" in key or "plate" in key:
        return (
            ("matched", "Placa coincide con OCR")
            if compare_plate(manual_value, ocr_value)
            else ("mismatch", "Placa no coincide con OCR")
        )

    if "serial" in key or "serie" in key:
        return (
            ("matched", "Serie coincide con OCR")
            if compare_serial(manual_value, ocr_value)
            else ("mismatch", "Serie no coincide con OCR")
        )

    if expected in NUMERIC_TYPES:
        return (
            ("matched", "Valor numérico coincide con OCR")
            if compare_numeric(manual_value, ocr_value)
            else ("mismatch", "Valor numérico no coincide con OCR")
        )

    left = _normalize_generic(manual_value)
    right = _normalize_generic(ocr_value)

    if left and left == right:
        return "matched", "Campo coincide con OCR"

    similarity = _similarity(manual_value, ocr_value)
    if similarity >= 0.88:
        return "matched", "Campo coincide con OCR por similitud alta"

    if similarity >= 0.72:
        return "mismatch", "Campo cercano al OCR pero requiere revisión manual"

    return "mismatch", "Campo no coincide con OCR"


def _field_priority_tokens(field_key: str, field_label: str | None) -> list[str]:
    joined = _normalize_soft(f"{field_key} {field_label or ''}")

    technical_terms = [
        "EMPRESA", "ESPECIALIDAD", "MARCA", "PAIS", "ORIGEN", "ANIO", "AÑO",
        "SERIE", "EJES", "CARROCERIA", "MODELO", "PESO", "CARGA"
    ]

    if any(term in joined for term in technical_terms):
        return ["PLACA TECNICA", "PLACA TÉCNICA", "PLATETECHNICAL", "FABRICACION", "FABRICACIÓN"]

    if "PLACA" in joined or "PLATE" in joined:
        return ["PLACA VEHICULAR", "PLATEVEHICLE", "RODAJE", "PLACA TECNICA"]

    if "VIN" in joined:
        return ["PLACA VEHICULAR", "PLATEVEHICLE", "PLACA TECNICA", "PLATETECHNICAL"]

    return ["PLACA TECNICA", "PLACA VEHICULAR", "PLATETECHNICAL", "PLATEVEHICLE"]


def _evidence_bonus(field_key: str, field_label: str | None, evidence_category: str | None, caption: str | None) -> float:
    joined = _normalize_soft(f"{evidence_category or ''} {caption or ''}")
    tokens = _field_priority_tokens(field_key, field_label)

    for idx, token in enumerate(tokens):
        if _normalize_soft(token) in joined:
            return max(0.18 - (idx * 0.05), 0.03)

    return 0.0


def _pick_best_candidate(field, evidence_pool: list[dict], aggregated_text: str) -> tuple[str | None, float | None, str]:
    candidates = []

    for item in evidence_pool:
        text = item["text"]
        if not text:
            continue

        candidate = _extract_candidate(
            field_key=field.field_key,
            field_label=field.field_label,
            expected_type=field.expected_type,
            text=text,
            manual_value=field.manual_value,
        )

        if not candidate:
            continue

        sim = _similarity(field.manual_value, candidate)
        conf = item["confidence"] or 0.0
        bonus = _evidence_bonus(field.field_key, field.field_label, item["evidence_category"], item["caption"])
        score = round((conf / 100.0) * 0.55 + sim * 0.30 + bonus, 4)

        candidates.append(
            {
                "ocr_value": candidate,
                "confidence": item["confidence"],
                "score": score,
                "source": f"evidence:{item['evidence_id']}",
            }
        )

    fallback_candidate = _extract_candidate(
        field_key=field.field_key,
        field_label=field.field_label,
        expected_type=field.expected_type,
        text=aggregated_text,
        manual_value=field.manual_value,
    )

    if fallback_candidate:
        sim = _similarity(field.manual_value, fallback_candidate)
        candidates.append(
            {
                "ocr_value": fallback_candidate,
                "confidence": None,
                "score": round(sim * 0.40, 4),
                "source": "aggregated_text",
            }
        )

    if not candidates:
        return None, None, "Sin candidato OCR"

    best = max(candidates, key=lambda item: item["score"])
    return best["ocr_value"], best["confidence"], f"Candidato tomado de {best['source']} con score {best['score']}"


def _is_priority_category(value: str | None) -> bool:
    soft = _normalize_soft(value)
    generic = _normalize_generic(value)

    return (
        soft in {"PLACA TECNICA", "PLACA TÉCNICA", "PLACA VEHICULAR", "PLACA VEHICULO"}
        or generic in {"PLATETECHNICAL", "PLATEVEHICLE", "PLACATECNICA", "PLACAVEHICULAR"}
    )


def validate_inspection_ocr(db: Session, inspection_id: int) -> dict | None:
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
        return None

    image_evidences = [
        evidence for evidence in inspection.evidences
        if evidence.file_type and evidence.file_type.lower().startswith("image/")
    ]

    priority_evidences = [
        evidence for evidence in image_evidences
        if _is_priority_category(evidence.evidence_category)
    ]

    if priority_evidences:
        image_evidences = priority_evidences

    if not image_evidences:
        raise ValueError("La inspección no tiene evidencias de imagen para OCR")

    extracted_chunks = []
    confidence_values = []
    evidence_pool = []

    for evidence in image_evidences:
        if evidence.ocr_processed and evidence.ocr_extracted_text:
            text = evidence.ocr_extracted_text
            confidence = float(evidence.ocr_confidence) if evidence.ocr_confidence is not None else None
        else:
            result = extract_text_from_evidence_record(db, evidence)
            text = result["extracted_text"]
            confidence = result["confidence"]

        evidence_pool.append(
            {
                "evidence_id": evidence.id,
                "text": text,
                "confidence": confidence,
                "evidence_category": evidence.evidence_category,
                "caption": getattr(evidence, "caption", None),
            }
        )

        if text:
            extracted_chunks.append(text)
        if confidence is not None:
            confidence_values.append(confidence)

    aggregated_text = "\n".join(extracted_chunks).strip()
    average_confidence = round(sum(confidence_values) / len(confidence_values), 2) if confidence_values else None

    results = []
    matched = 0
    mismatched = 0
    not_found = 0

    for field in inspection.fields:
        ocr_value, field_confidence, candidate_message = _pick_best_candidate(
            field=field,
            evidence_pool=evidence_pool,
            aggregated_text=aggregated_text,
        )

        validation_status, validation_message = _compare_values(
            field_key=field.field_key,
            expected_type=field.expected_type,
            manual_value=field.manual_value,
            ocr_value=ocr_value,
        )

        field.ocr_value = ocr_value
        field.validation_status = validation_status
        field.validation_message = f"{validation_message}. {candidate_message}"
        field.confidence = field_confidence if field_confidence is not None else average_confidence

        if validation_status == "matched":
            matched += 1
            if ocr_value:
                field.final_value = ocr_value
        elif validation_status == "mismatch":
            mismatched += 1
            if not field.final_value:
                field.final_value = field.manual_value
        else:
            not_found += 1
            if not field.final_value:
                field.final_value = field.manual_value

        results.append(
            {
                "field_id": field.id,
                "field_key": field.field_key,
                "field_label": field.field_label,
                "manual_value": field.manual_value,
                "ocr_value": field.ocr_value,
                "final_value": field.final_value,
                "validation_status": field.validation_status,
                "validation_message": field.validation_message,
                "confidence": float(field.confidence) if field.confidence is not None else None,
            }
        )

    db.commit()

    return {
        "inspection_id": inspection.id,
        "processed_evidences": len(image_evidences),
        "aggregated_text": aggregated_text,
        "summary": {
            "matched": matched,
            "mismatched": mismatched,
            "not_found": not_found,
            "average_confidence": average_confidence,
        },
        "results": results,
    }