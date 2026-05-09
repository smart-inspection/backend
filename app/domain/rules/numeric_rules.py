import re

NUMERIC_PATTERN = re.compile(r"\b\d+(?:[.,]\d+)?\b")

def normalize_numeric(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^\d]", "", value)

def find_numeric_value(text: str | None, manual_hint: str | None = None) -> str | None:
    if not text:
        return None

    if manual_hint:
        normalized_hint = normalize_numeric(manual_hint)
        normalized_text = normalize_numeric(text)
        if normalized_hint and normalized_hint in normalized_text:
            return normalized_hint

        matches = NUMERIC_PATTERN.findall(text)
        if not matches:
            return None

        return matches[0]

def compare_numeric(manual_value: str | None, ocr_value: str | None) -> bool:
    left = normalize_numeric(manual_value)
    right = normalize_numeric(ocr_value)
    return bool(left) and left == right