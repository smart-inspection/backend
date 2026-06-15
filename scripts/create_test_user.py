# scripts/create_test_user.py
from app.db.session import SessionLocal
from app.db.models.users import User
from app.core.security import get_password_hash

db = SessionLocal()

admin = User(
    full_name="Admin Demo",
    email="admin@smartinspect.com",
    password_hash=get_password_hash("admin1234"),
    role="admin",
    is_active=True,
)
inspector = User(
    full_name="Inspector Demo",
    email="inspector@smartinspect.com",
    password_hash=get_password_hash("inspector1234"),
    role="inspector",
    is_active=True,
)

db.add(admin)
db.add(inspector)
db.commit()
db.close()
print("Usuarios creados.")