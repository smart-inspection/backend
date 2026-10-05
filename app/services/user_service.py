from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.db.models.users import User
from app.db.models.inspection import Inspection
from app.schemas.users import UserCreate, UserUpdate

VALID_ROLES = {"admin", "inspector", "viewer"}


def list_users(db: Session) -> list[User]:
    return db.query(User).order_by(User.id).all()


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email.strip().lower()).first()


def create_user(db: Session, payload: UserCreate) -> User:
    if payload.role not in VALID_ROLES:
        raise ValueError(f"Rol inválido: {payload.role}. Roles permitidos: {', '.join(VALID_ROLES)}")

    if get_user_by_email(db, payload.email):
        raise ValueError(f"Ya existe un usuario con el correo {payload.email}")

    user = User(
        full_name=payload.full_name.strip(),
        email=payload.email.strip().lower(),
        password_hash=get_password_hash(payload.password),
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user(db: Session, user_id: int, payload: UserUpdate) -> User | None:
    user = get_user_by_id(db, user_id)
    if not user:
        return None

    if payload.full_name is not None:
        user.full_name = payload.full_name.strip()

    if payload.role is not None:
        if payload.role not in VALID_ROLES:
            raise ValueError(f"Rol inválido: {payload.role}")
        user.role = payload.role

    if payload.is_active is not None:
        user.is_active = payload.is_active

    try:
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        raise
    return user


STATUSES_ACTIVOS = {"draft", "in_review", "observed"}


def eliminar_usuario(db: Session, user_id: int) -> bool:
    """
    Elimina un usuario.
    - Bloquea si tiene inspecciones en estado activo (draft/in_review/observed).
    - Si solo tiene inspecciones finalizadas, desvincula responsible_inspector_id
      antes de borrar para evitar FK violation en PostgreSQL.
    Retorna True si fue eliminado, False si no existía.
    """
    user = get_user_by_id(db, user_id)
    if not user:
        return False

    inspecciones_activas = (
        db.query(Inspection)
        .filter(
            Inspection.responsible_inspector_id == user_id,
            Inspection.status.in_(STATUSES_ACTIVOS),
        )
        .count()
    )
    if inspecciones_activas > 0:
        raise ValueError(
            f"El usuario tiene {inspecciones_activas} inspección(es) activa(s) asignada(s). "
            "Reasigna o finaliza las inspecciones antes de eliminar el usuario."
        )

    # Desvincular inspector de inspecciones finalizadas para liberar la FK
    db.query(Inspection).filter(
        Inspection.responsible_inspector_id == user_id
    ).update({"responsible_inspector_id": None}, synchronize_session="fetch")

    try:
        db.delete(user)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return True