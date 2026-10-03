"""Pruebas unitarias para el módulo de criptografía y trazabilidad PDP (Ley N° 29733)."""

import pytest
from app.core.cryptography import decrypt_field, encrypt_field


def test_encrypt_and_decrypt_field():
    original = "987654321"
    encrypted = encrypt_field(original)

    assert encrypted is not None
    assert encrypted != original
    assert encrypted.startswith("gAAAAA")

    decrypted = decrypt_field(encrypted)
    assert decrypted == original


def test_encrypt_decrypt_handles_none_and_empty():
    assert encrypt_field(None) is None
    assert decrypt_field(None) is None
    assert encrypt_field("") == ""
    assert decrypt_field("") == ""


def test_decrypt_legacy_plaintext_fallback():
    # Datos en texto plano previos a la migración se leen sin fallar
    legacy_text = "antiguo@correo.com"
    result = decrypt_field(legacy_text)
    assert result == legacy_text
