from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    decode_access_token,
    verify_password,
    TokenDecodeError,
)
from app.db.models.users import User


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if not user:
        return None
    if not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def create_token_for_user(user: User) -> str:
    return create_access_token(
        subject=user.id,
        extra_claims={"role": user.role, "email": user.email},
    )


def get_user_from_token(db: Session, token: str) -> User | None:
    try:
        payload = decode_access_token(token)
    except TokenDecodeError:
        return None

    user_id_raw = payload.get("sub")
    if user_id_raw is None:
        return None

    try:
        user_id = int(user_id_raw)
    except (ValueError, TypeError):
        return None

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    return user