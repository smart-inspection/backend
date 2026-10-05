"""Módulo de utilidades criptográficas y cifrado simétrico en reposo (AES-256 Fernet).

Cumple con los requerimientos de seguridad de datos personales de la Ley N° 29733.
"""

from __future__ import annotations

import logging
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import String, TypeDecorator

from app.core.config import settings

logger = logging.getLogger(__name__)

_cipher: Fernet | None = None


def get_cipher() -> Fernet:
    """Retorna o inicializa la instancia singleton de Fernet para cifrado de campos."""
    global _cipher
    if _cipher is None:
        key = getattr(settings, "field_encryption_key", None)
        if not key:
            raise ValueError(
                "La clave maestra FIELD_ENCRYPTION_KEY no está configurada en settings."
            )
        raw_key = key.encode("utf-8") if isinstance(key, str) else key
        _cipher = Fernet(raw_key)
    return _cipher


def encrypt_field(value: str | None) -> str | None:
    """Cifra un valor de texto usando AES-256 (Fernet).

    Maneja nulos y cadenas vacías de forma segura.
    """
    if value is None:
        return None
    normalized = str(value)
    if not normalized:
        return normalized
    cipher = get_cipher()
    encrypted_bytes = cipher.encrypt(normalized.encode("utf-8"))
    return encrypted_bytes.decode("utf-8")


def decrypt_field(value: str | None) -> str | None:
    """Descifra un valor previamente cifrado.

    Si el valor es None o falla el descifrado (ej. datos existentes en texto plano),
    retorna el valor original de forma defensiva para evitar caídas de lectura.
    """
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        return value
    try:
        cipher = get_cipher()
        decrypted_bytes = cipher.decrypt(value.encode("utf-8"))
        return decrypted_bytes.decode("utf-8")
    except (InvalidToken, Exception) as exc:
        logger.warning(
            "No fue posible descifrar el valor mediante Fernet; retornando texto original: %s",
            exc,
        )
        return value


class EncryptedString(TypeDecorator):
    """TypeDecorator de SQLAlchemy para cifrado simétrico transparente en reposo.

    Cifra en `process_bind_param` (inserción/actualización) y descifra en
    `process_result_value` (lectura).
    """

    impl = String
    cache_ok = True

    def __init__(self, length: int = 255, *args: Any, **kwargs: Any) -> None:
        super().__init__(length, *args, **kwargs)

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        return encrypt_field(str(value))

    def process_result_value(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        return decrypt_field(str(value))
