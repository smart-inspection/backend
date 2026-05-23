import re

PLATE_PATTERNS = [
    re.compile(r"\b[A-Z0-9]{3}[-\s]?[A-Z0-9]{3,4}\b", re.IGNORECASE),
    re.compile(r"\b[A-Z]{1,3}[-\s]?\d{3,4}\b", re.IGNORECASE),
]

def normalize_plate(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^A-Z0-9]", "", value.upper())

def find_plate(text: str | None) -> str | None:
    if not text:
        return None

    for pattern in PLATE_PATTERNS:
        match = pattern.search(text.upper())
        if match:
            return normalize_plate(match.group(0))

    return None

def compare_plate(manual_value: str | None, ocr_value: str | None) -> bool:
    left = normalize_plate(manual_value)
    right = normalize_plate(ocr_value)
    return bool(left) and left == right