from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app.models import RoleEnum, User
from app.services import create_product, create_user


def seed() -> None:
    settings = get_settings()
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        demo_users = [
            {
                "email": settings.default_admin_email,
                "full_name": settings.default_admin_name,
                "password_hash": hash_password(settings.default_admin_password),
                "role": RoleEnum.admin,
            },
            {
                "email": "manager@example.com",
                "full_name": "Demo Manager",
                "password_hash": hash_password("manager123"),
                "role": RoleEnum.manager,
            },
            {
                "email": "operator@example.com",
                "full_name": "Demo Operator",
                "password_hash": hash_password("operator123"),
                "role": RoleEnum.operator,
            },
        ]

        for payload in demo_users:
            existing_user = db.scalar(select(User).where(User.email == payload["email"]))
            if existing_user:
                continue
            create_user(db, **payload)

        products = [
            {
                "sku": "IPH15-128-BLK",
                "name": "iPhone 15 128GB Black",
                "description": "Flagship smartphone for demo inventory",
                "price": "799.00",
                "initial_quantity": 24,
            },
            {
                "sku": "AIRPODS-PRO-2",
                "name": "AirPods Pro 2",
                "description": "Wireless earphones for demo orders",
                "price": "249.00",
                "initial_quantity": 8,
            },
            {
                "sku": "MBP14-M4-BASE",
                "name": "MacBook Pro 14 M4",
                "description": "High-ticket item to demonstrate order totals",
                "price": "1999.00",
                "initial_quantity": 5,
            },
        ]

        for product in products:
            try:
                create_product(db, **product)
            except Exception:
                db.rollback()


if __name__ == "__main__":
    seed()
