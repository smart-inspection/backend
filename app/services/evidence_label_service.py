import re
import unicodedata
from dataclasses import dataclass
from typing import Any

@dataclass
class EvidenceLabelResult:
    raw_label: str | None
    normalized_label: str | None
    evidence_slot: str | None
    component_code: str | None
    axle_number: int | None
    side: str | None
    is_reference: bool
    label_confidence: float | None
    metadata_json: dict[str, Any] | None

def normalize_text(value: str | None) -> str | None:
    if value is None:
        return None

    text = unicodedata.normalize("NFKD", value)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None

def infer_side(normalized_label: str | None, side: str | None = None) -> str | None:
    if side:
        side_value = normalize_text(side)
        if side_value in {"left", "right", "center"}:
            return side_value

    if not normalized_label:
        return None

    if any(token in normalized_label for token in ["izq", "izquierdo", "left"]):
        return "left"
    if any(token in normalized_label for token in ["der", "derecho", "right"]):
        return "right"
    if "centro" in normalized_label or "center" in normalized_label:
        return "center"

    return None

def infer_axle_number(normalized_label: str | None, axle_number: int | None = None) -> int | None:
    if axle_number is not None:
        return axle_number

    if not normalized_label:
        return None

    match = re.search(r"\b([1-9])\b", normalized_label)
    if match:
        return int(match.group(1))

    return None

def build_slot(
    normalized_label: str | None,
    component_code: str | None = None,
    axle_number: int | None = None,
    side: str | None = None,
    is_reference: bool = False,
) -> EvidenceLabelResult:
    raw_component = normalize_text(component_code)
    normalized_side = infer_side(normalized_label, side)
    normalized_axle = infer_axle_number(normalized_label, axle_number)

    if not normalized_label and not raw_component:
        return EvidenceLabelResult(
            raw_label=None,
            normalized_label=None,
            evidence_slot=None,
            component_code=None,
            axle_number=normalized_axle,
            side=normalized_side,
            is_reference=is_reference,
            label_confidence=None,
            metadata_json=None,
        )

    text = normalized_label or ""

    if ("semirremolque" in text or "semiremolque" in text) and normalized_side in ("left", "right"):
        return EvidenceLabelResult(
            raw_label=None,
            normalized_label=normalized_label,
            evidence_slot=f"semitrailer_{normalized_side}",
            component_code="semitrailer",
            axle_number=None,
            side=normalized_side,
            is_reference=is_reference,
            label_confidence=0.94,
            metadata_json={"reason": "matched_semitrailer_side"},
        )

    if "portada" in text or "semirremolque completo" in text or "vista general" in text:
        return EvidenceLabelResult(
            raw_label=None,
            normalized_label=normalized_label,
            evidence_slot="cover_semitrailer",
            component_code="semitrailer",
            axle_number=None,
            side=None,
            is_reference=is_reference,
            label_confidence=0.98,
            metadata_json={"reason": "matched_cover"},
        )

    if "placa tecnica" in text or "placa de fabrica" in text or "placa de identificacion" in text:
        return EvidenceLabelResult(
            raw_label=None,
            normalized_label=normalized_label,
            evidence_slot="plate_technical",
            component_code="plate",
            axle_number=None,
            side=None,
            is_reference=is_reference,
            label_confidence=0.98,
            metadata_json={"reason": "matched_technical_plate"},
        )

    if text == "placa" or "placa vehicular" in text:
        return EvidenceLabelResult(
            raw_label=None,
            normalized_label=normalized_label,
            evidence_slot="plate_vehicle",
            component_code="plate",
            axle_number=None,
            side=None,
            is_reference=is_reference,
            label_confidence=0.96,
            metadata_json={"reason": "matched_vehicle_plate"},
        )

    if "plancha king pin" in text or "plancha de king pin" in text:
        return EvidenceLabelResult(
            raw_label=None,
            normalized_label=normalized_label,
            evidence_slot="kingpin_plate_subject",
            component_code="kingpin_plate",
            axle_number=None,
            side=None,
            is_reference=is_reference,
            label_confidence=0.97,
            metadata_json={"reason": "matched_kingpin_plate"},
        )

    if "king pin referencia" in text or "kingpin referencia" in text or ("king pin" in text and is_reference):
        return EvidenceLabelResult(
            raw_label=None,
            normalized_label=normalized_label,
            evidence_slot="kingpin_reference",
            component_code="kingpin",
            axle_number=None,
            side=None,
            is_reference=True,
            label_confidence=0.97,
            metadata_json={"reason": "matched_kingpin_reference"},
        )

    if "king pin" in text or "kingpin" in text:
        return EvidenceLabelResult(
            raw_label=None,
            normalized_label=normalized_label,
            evidence_slot="kingpin_subject",
            component_code="kingpin",
            axle_number=None,
            side=None,
            is_reference=is_reference,
            label_confidence=0.96,
            metadata_json={"reason": "matched_kingpin"},
        )

    if "balancin" in text or "balancin" in text:
        return EvidenceLabelResult(
            raw_label=None,
            normalized_label=normalized_label,
            evidence_slot="balancer",
            component_code="balancer",
            axle_number=None,
            side=None,
            is_reference=is_reference,
            label_confidence=0.95,
            metadata_json={"reason": "matched_balancer"},
        )

    if "soporte de muelle" in text or "soporte muelle" in text or "muelle" in text or "bolsa de aire" in text:
        return EvidenceLabelResult(
            raw_label=None,
            normalized_label=normalized_label,
            evidence_slot="spring_support",
            component_code="spring_support",
            axle_number=None,
            side=None,
            is_reference=is_reference,
            label_confidence=0.93,
            metadata_json={"reason": "matched_spring_support"},
        )

    if "chasis" in text or "plataforma" in text:
        return EvidenceLabelResult(
            raw_label=None,
            normalized_label=normalized_label,
            evidence_slot="chassis_general",
            component_code="chassis",
            axle_number=None,
            side=None,
            is_reference=is_reference,
            label_confidence=0.94,
            metadata_json={"reason": "matched_chassis"},
        )

    if "munon" in text or "muñon" in text or raw_component == "journal":
        if normalized_axle and normalized_side:
            return EvidenceLabelResult(
                raw_label=None,
                normalized_label=normalized_label,
                evidence_slot=f"journal_{normalized_axle}_{normalized_side}",
                component_code="journal",
                axle_number=normalized_axle,
                side=normalized_side,
                is_reference=is_reference,
                label_confidence=0.95,
                metadata_json={"reason": "matched_journal"},
            )

    if "punta de eje" in text or "eje" in text or raw_component == "axle_end":
        if normalized_axle and normalized_side:
            return EvidenceLabelResult(
                raw_label=None,
                normalized_label=normalized_label,
                evidence_slot=f"axle_{normalized_axle}_{normalized_side}_end",
                component_code="axle_end",
                axle_number=normalized_axle,
                side=normalized_side,
                is_reference=is_reference,
                label_confidence=0.95,
                metadata_json={"reason": "matched_axle_end"},
            )

    return EvidenceLabelResult(
        raw_label=None,
        normalized_label=normalized_label,
        evidence_slot=None,
        component_code=raw_component,
        axle_number=normalized_axle,
        side=normalized_side,
        is_reference=is_reference,
        label_confidence=0.40 if normalized_label else None,
        metadata_json={"reason": "unmatched_label"},
    )

def resolve_evidence_label(
    raw_label: str | None,
    component_code: str | None = None,
    axle_number: int | None = None,
    side: str | None = None,
    is_reference: bool = False,
) -> EvidenceLabelResult:
    normalized_label = normalize_text(raw_label)
    result = build_slot(
        normalized_label=normalized_label,
        component_code=component_code,
        axle_number=axle_number,
        side=side,
        is_reference=is_reference,
    )
    result.raw_label = raw_label
    return result