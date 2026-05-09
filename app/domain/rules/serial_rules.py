import re

from pip._internal.resolution.resolvelib import candidates

SERIAL_LABEL_PATTERN = re.compile(
    r"(?:serial|serie|nro\.?\s*serie|numero\s*de\s*serie|número\s*de\s*serie)\s*[:\-]?\s*([A-Z0-9\-]{5,30})",
    re.IGNORECASE,
)

GENERIC_SERIAL_PATTERN = re.compile(r"\b[A-Z0-9\-]{6,30}\b", re.IGNORECASE)

def normalize_serial(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^A-Z0-9]", "", value.upper())

def find_serial(text: str | None, manual_hint: str | None = None) -> str | None:
    if not text:
        return None

    labeled = SERIAL_LABEL_PATTERN.search(text)
    if labeled:
        return normalize_serial(labeled.group(1))

    if manual_hint:
        normalized_hint = normalize_serial(manual_hint)
        normalized_text = normalize_serial(text)
        if normalized_hint and normalized_hint in normalized_text:
            return normalized_hint

    candidates = GENERIC_SERIAL_PATTERN.findall(text.upper())
    if not candidates:
        return None

    candidates = sorted(candidates, key=len, reverse=True)
    return normalize_serial(candidates[0])

def compare_serial(manual_value: str | None, ocr_value: str | None) -> bool:
    left = normalize_serial(manual_value)
    right = normalize_serial(ocr_value)
    return bool(left) and left == right