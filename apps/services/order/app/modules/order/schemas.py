import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.modules.order.internal.models import Order


class CheckoutRequest(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=200)


class OrderItemOut(BaseModel):
    book_id: uuid.UUID
    title_snapshot: str
    unit_price: Decimal
    quantity: int
    line_total: Decimal

    model_config = {"from_attributes": True}


class OrderOut(BaseModel):
    id: uuid.UUID
    status: str
    total_amount: Decimal
    created_at: datetime
    items: list[OrderItemOut]

    @classmethod
    def from_model(cls, order: Order) -> "OrderOut":
        return cls(
            id=order.id,
            status=order.status,
            total_amount=order.total_amount,
            created_at=order.created_at,
            items=[OrderItemOut.model_validate(item) for item in order.items],
        )
