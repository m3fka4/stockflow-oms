from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.realtime import manager
from app.deps import get_current_user, require_roles
from app.models import Order, RoleEnum, User
from app.schemas import OrderCreate, OrderRead, OrderStatusUpdate
from app.services import create_order, get_order_or_404, update_order_status

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.get("", response_model=list[OrderRead])
def list_orders(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(RoleEnum.admin, RoleEnum.manager, RoleEnum.operator)),
) -> list[Order]:
    statement = (
        select(Order)
        .options(joinedload(Order.items), joinedload(Order.status_history))
        .order_by(Order.created_at.desc())
    )
    return list(db.scalars(statement).unique().all())


@router.get("/{order_id}", response_model=OrderRead)
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(RoleEnum.admin, RoleEnum.manager, RoleEnum.operator)),
) -> Order:
    return get_order_or_404(db, order_id)


@router.post("", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
def create_order_endpoint(
    payload: OrderCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Order:
    order = create_order(
        db,
        customer_name=payload.customer_name,
        customer_email=payload.customer_email,
        items=[item.model_dump() for item in payload.items],
        created_by_id=current_user.id,
    )
    background_tasks.add_task(
        manager.broadcast,
        {
            "event_type": "order.created",
            "entity": "order",
            "payload": {"order_id": order.id, "number": order.number, "status": order.status},
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    return order


@router.patch("/{order_id}/status", response_model=OrderRead)
def update_order_status_endpoint(
    order_id: int,
    payload: OrderStatusUpdate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_roles(RoleEnum.admin, RoleEnum.manager, RoleEnum.operator)),
    db: Session = Depends(get_db),
) -> Order:
    order_statement = (
        select(Order)
        .where(Order.id == order_id)
        .options(joinedload(Order.items), joinedload(Order.status_history))
    )
    order = db.execute(order_statement).unique().scalar_one_or_none()
    if not order:
        return get_order_or_404(db, order_id)

    order = update_order_status(db, order=order, new_status=payload.status, changed_by_id=current_user.id)
    background_tasks.add_task(
        manager.broadcast,
        {
            "event_type": "order.status_updated",
            "entity": "order",
            "payload": {"order_id": order.id, "number": order.number, "status": order.status},
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    return order
