import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.order.internal.models import Order, OrderItem


def get_by_idempotency_key(db: Session, idempotency_key: str) -> Order | None:
    return db.scalar(select(Order).where(Order.idempotency_key == idempotency_key))


def get_by_id(db: Session, order_id: uuid.UUID) -> Order | None:
    return db.get(Order, order_id)


def list_for_user(db: Session, user_id: uuid.UUID) -> list[Order]:
    stmt = (
        select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc())
    )
    return list(db.scalars(stmt).unique().all())


class LineItemInput:
    __slots__ = ("book_id", "title", "unit_price", "quantity")

    def __init__(self, book_id: uuid.UUID, title: str, unit_price: Decimal, quantity: int):
        self.book_id = book_id
        self.title = title
        self.unit_price = unit_price
        self.quantity = quantity


def create_order(
    db: Session,
    *,
    user_id: uuid.UUID,
    idempotency_key: str,
    line_items: list[LineItemInput],
) -> Order:
    total = sum((item.unit_price * item.quantity for item in line_items), Decimal("0"))
    # Generated explicitly rather than relying on the model's default=uuid.uuid4, which
    # SQLAlchemy only resolves at flush time - order.id would still be None here otherwise.
    order_id = uuid.uuid4()
    order = Order(
        id=order_id,
        user_id=user_id,
        idempotency_key=idempotency_key,
        total_amount=total,
        status="completed",
    )
    db.add(order)
    for item in line_items:
        db.add(
            OrderItem(
                order_id=order_id,
                book_id=item.book_id,
                title_snapshot=item.title,
                unit_price=item.unit_price,
                quantity=item.quantity,
                line_total=item.unit_price * item.quantity,
            )
        )
    db.commit()
    db.refresh(order)
    return order
