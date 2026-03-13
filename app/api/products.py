from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.database import get_db
from app.core.realtime import manager
from app.deps import require_roles
from app.models import Product, RoleEnum, User
from app.schemas import InventoryUpdate, ProductCreate, ProductRead, ProductUpdate
from app.services import create_product, update_inventory

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("", response_model=list[ProductRead])
def list_products(db: Session = Depends(get_db), _: User = Depends(require_roles(RoleEnum.admin, RoleEnum.manager, RoleEnum.operator))) -> list[Product]:
    statement = select(Product).options(joinedload(Product.inventory_item)).order_by(Product.created_at.desc())
    return list(db.scalars(statement).unique().all())


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_product_endpoint(
    payload: ProductCreate,
    background_tasks: BackgroundTasks,
    _: User = Depends(require_roles(RoleEnum.admin, RoleEnum.manager)),
    db: Session = Depends(get_db),
) -> Product:
    product = create_product(
        db,
        sku=payload.sku,
        name=payload.name,
        description=payload.description,
        price=payload.price,
        initial_quantity=payload.initial_quantity,
    )
    background_tasks.add_task(
        manager.broadcast,
        {
            "event_type": "product.created",
            "entity": "product",
            "payload": {"product_id": product.id, "sku": product.sku, "name": product.name},
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    return product


@router.patch("/{product_id}", response_model=ProductRead)
def update_product(
    product_id: int,
    payload: ProductUpdate,
    _: User = Depends(require_roles(RoleEnum.admin, RoleEnum.manager)),
    db: Session = Depends(get_db),
) -> Product:
    statement = select(Product).where(Product.id == product_id).options(joinedload(Product.inventory_item))
    product = db.scalar(statement)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(product, field, value)
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.patch("/{product_id}/inventory", response_model=ProductRead)
def update_product_inventory(
    product_id: int,
    payload: InventoryUpdate,
    background_tasks: BackgroundTasks,
    _: User = Depends(require_roles(RoleEnum.admin, RoleEnum.manager, RoleEnum.operator)),
    db: Session = Depends(get_db),
) -> Product:
    statement = select(Product).where(Product.id == product_id).options(joinedload(Product.inventory_item))
    product = db.scalar(statement)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    product = update_inventory(db, product=product, quantity=payload.quantity, reserved=payload.reserved)
    background_tasks.add_task(
        manager.broadcast,
        {
            "event_type": "inventory.updated",
            "entity": "inventory",
            "payload": {
                "product_id": product.id,
                "sku": product.sku,
                "quantity": product.inventory_item.quantity if product.inventory_item else 0,
                "reserved": product.inventory_item.reserved if product.inventory_item else 0,
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    return product


@router.get("/low-stock", response_model=list[ProductRead])
def low_stock_products(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(RoleEnum.admin, RoleEnum.manager, RoleEnum.operator)),
) -> list[Product]:
    settings = get_settings()
    statement = (
        select(Product)
        .join(Product.inventory_item)
        .options(joinedload(Product.inventory_item))
        .where(Product.is_active.is_(True))
        .where(Product.inventory_item.has())
        .order_by(Product.updated_at.desc())
    )
    products = list(db.scalars(statement).unique().all())
    return [product for product in products if product.inventory_item and product.inventory_item.quantity <= settings.low_stock_threshold]
