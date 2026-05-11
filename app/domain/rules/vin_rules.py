import re

VIN_PATTERN = re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b", re.IGNORECASE)

def normalize_vin(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^A-Z0-9]", "", value.upper())

def find_vin(text:str | None) -> str | None:
    if not text:
        return None
    match = VIN_PATTERN.search(text.upper())
    if not match:
        return None
    return normalize_vin(match.group(0))

def compare_vin(manual_value: str | None, orc_value: str | None) -> bool:
    left = normalize_vin(manual_value)
    right = normalize_vin(orc_value)
    return bool(left) and left == right