from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models import InventoryItem, Order, OrderItem, OrderStatus, Product, RoleEnum, StatusHistory, User

ALLOWED_STATUS_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.pending: {OrderStatus.confirmed, OrderStatus.cancelled},
    OrderStatus.confirmed: {OrderStatus.processing, OrderStatus.cancelled},
    OrderStatus.processing: {OrderStatus.shipped, OrderStatus.cancelled},
    OrderStatus.shipped: {OrderStatus.completed},
    OrderStatus.completed: set(),
    OrderStatus.cancelled: set(),
}


def create_user(db: Session, *, email: str, full_name: str, password_hash: str, role: RoleEnum) -> User:
    existing = db.scalar(select(User).where(User.email == email))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with this email already exists")

    user = User(email=email, full_name=full_name, password_hash=password_hash, role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_product(
    db: Session,
    *,
    sku: str,
    name: str,
    description: str | None,
    price: Decimal,
    initial_quantity: int,
) -> Product:
    existing = db.scalar(select(Product).where(Product.sku == sku))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Product with this SKU already exists")

    product = Product(sku=sku, name=name, description=description, price=price)
    inventory = InventoryItem(product=product, quantity=initial_quantity, reserved=0)
    db.add_all([product, inventory])
    db.commit()
    db.refresh(product)
    return product


def update_inventory(db: Session, *, product: Product, quantity: int, reserved: int | None = None) -> Product:
    if not product.inventory_item:
        product.inventory_item = InventoryItem(quantity=0, reserved=0)

    product.inventory_item.quantity = quantity
    if reserved is not None:
        product.inventory_item.reserved = reserved
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def _build_order_number() -> str:
    return f"ORD-{datetime.now(timezone.utc):%Y%m%d}-{uuid4().hex[:8].upper()}"


def create_order(db: Session, *, customer_name: str, customer_email: str, items: list[dict], created_by_id: int) -> Order:
    order = Order(
        number=_build_order_number(),
        customer_name=customer_name,
        customer_email=customer_email,
        created_by_id=created_by_id,
        status=OrderStatus.pending,
    )

    total_amount = Decimal("0.00")
    order_items: list[OrderItem] = []
    inventory_updates: list[InventoryItem] = []

    for item in items:
        product = db.get(Product, item["product_id"])
        if not product or not product.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product {item['product_id']} not found or inactive",
            )
        inventory = product.inventory_item
        if not inventory:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Inventory for SKU {product.sku} not initialized")
        available = inventory.quantity - inventory.reserved
        if available < item["quantity"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Not enough stock for SKU {product.sku}. Available: {available}",
            )

        line_total = product.price * item["quantity"]
        total_amount += line_total
        inventory.reserved += item["quantity"]
        inventory_updates.append(inventory)
        order_items.append(
            OrderItem(
                product_id=product.id,
                quantity=item["quantity"],
                unit_price=product.price,
                line_total=line_total,
            )
        )

    order.total_amount = total_amount
    order.items = order_items
    order.status_history = [StatusHistory(old_status=None, new_status=OrderStatus.pending, changed_by_id=created_by_id)]

    db.add(order)
    for inventory in inventory_updates:
        db.add(inventory)
    db.commit()
    db.refresh(order)
    return get_order_or_404(db, order.id)


def get_order_or_404(db: Session, order_id: int) -> Order:
    statement = (
        select(Order)
        .where(Order.id == order_id)
        .options(joinedload(Order.items), joinedload(Order.status_history))
    )
    order = db.execute(statement).unique().scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order


def update_order_status(db: Session, *, order: Order, new_status: OrderStatus, changed_by_id: int) -> Order:
    old_status = order.status
    if old_status == new_status:
        return get_order_or_404(db, order.id)
    if new_status not in ALLOWED_STATUS_TRANSITIONS[old_status]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status transition: {old_status} -> {new_status}",
        )

    order.status = new_status
    order.status_history.append(
        StatusHistory(old_status=old_status, new_status=new_status, changed_by_id=changed_by_id)
    )

    if new_status == OrderStatus.completed:
        for item in order.items:
            inventory = db.scalar(select(InventoryItem).where(InventoryItem.product_id == item.product_id))
            if inventory:
                inventory.quantity -= item.quantity
                inventory.reserved = max(inventory.reserved - item.quantity, 0)
                db.add(inventory)

    if new_status == OrderStatus.cancelled:
        for item in order.items:
            inventory = db.scalar(select(InventoryItem).where(InventoryItem.product_id == item.product_id))
            if inventory:
                inventory.reserved = max(inventory.reserved - item.quantity, 0)
                db.add(inventory)

    db.add(order)
    db.commit()
    return get_order_or_404(db, order.id)


def dashboard_summary(db: Session, *, low_stock_threshold: int) -> dict:
    total_products = db.scalar(select(func.count(Product.id))) or 0
    active_products = db.scalar(select(func.count(Product.id)).where(Product.is_active.is_(True))) or 0
    total_orders = db.scalar(select(func.count(Order.id))) or 0
    pending_orders = db.scalar(select(func.count(Order.id)).where(Order.status == OrderStatus.pending)) or 0
    completed_orders = db.scalar(select(func.count(Order.id)).where(Order.status == OrderStatus.completed)) or 0
    low_stock_products = (
        db.scalar(
            select(func.count(InventoryItem.id)).where(InventoryItem.quantity <= low_stock_threshold)
        )
        or 0
    )
    inventory_units = db.scalar(select(func.coalesce(func.sum(InventoryItem.quantity), 0))) or 0
    inventory_reserved = db.scalar(select(func.coalesce(func.sum(InventoryItem.reserved), 0))) or 0
    revenue_total = (
        db.scalar(
            select(func.coalesce(func.sum(Order.total_amount), 0)).where(Order.status == OrderStatus.completed)
        )
        or Decimal("0.00")
    )

    return {
        "total_products": total_products,
        "active_products": active_products,
        "total_orders": total_orders,
        "pending_orders": pending_orders,
        "completed_orders": completed_orders,
        "low_stock_products": low_stock_products,
        "inventory_units": inventory_units,
        "inventory_reserved": inventory_reserved,
        "revenue_total": revenue_total,
    }
