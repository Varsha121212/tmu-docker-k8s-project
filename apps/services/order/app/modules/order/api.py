from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_bearer_token, get_current_user_id
from app.modules.order import service
from app.modules.order.schemas import CheckoutRequest, OrderOut

router = APIRouter(prefix="/api/orders", tags=["order"])


@router.get("/health/ready")
def health_ready(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable"
        ) from exc
    return {"status": "ready"}


@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
def checkout(
    payload: CheckoutRequest,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
    token: str = Depends(get_bearer_token),
) -> OrderOut:
    try:
        order = service.checkout(
            db,
            user_id=current_user_id,
            token=token,
            idempotency_key=payload.idempotency_key,
        )
    except service.EmptyCartError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cart is empty"
        ) from exc
    except service.CheckoutRejectedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Insufficient stock"
        ) from exc
    return OrderOut.from_model(order)


@router.get("", response_model=list[OrderOut])
def list_orders(
    db: Session = Depends(get_db), current_user_id: str = Depends(get_current_user_id)
) -> list[OrderOut]:
    orders = service.list_orders_for_user(db, user_id=current_user_id)
    return [OrderOut.from_model(o) for o in orders]


@router.get("/{order_id}", response_model=OrderOut)
def get_order(
    order_id: str,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> OrderOut:
    order = service.get_order_for_user(db, user_id=current_user_id, order_id=order_id)
    if order is None:
        # Same response whether the order doesn't exist or belongs to someone else -
        # doesn't confirm existence of orders the caller doesn't own (US-ORD-05 ownership check).
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return OrderOut.from_model(order)
