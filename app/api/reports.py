from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.deps import require_roles
from app.models import InventoryItem, Product, RoleEnum, User
from app.schemas import DashboardSummary, LowStockItem
from app.services import dashboard_summary

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/dashboard", response_model=DashboardSummary)
def dashboard(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(RoleEnum.admin, RoleEnum.manager)),
) -> DashboardSummary:
    settings = get_settings()
    return DashboardSummary(**dashboard_summary(db, low_stock_threshold=settings.low_stock_threshold))


@router.get("/low-stock", response_model=list[LowStockItem])
def low_stock(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(RoleEnum.admin, RoleEnum.manager, RoleEnum.operator)),
) -> list[LowStockItem]:
    settings = get_settings()
    statement = select(Product, InventoryItem).join(InventoryItem, InventoryItem.product_id == Product.id)
    rows = db.execute(statement).all()
    result: list[LowStockItem] = []
    for product, inventory in rows:
        if inventory.quantity <= settings.low_stock_threshold:
            result.append(
                LowStockItem(
                    product_id=product.id,
                    sku=product.sku,
                    name=product.name,
                    quantity=inventory.quantity,
                    reserved=inventory.reserved,
                )
            )
    return result
