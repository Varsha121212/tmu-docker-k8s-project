import uuid
from decimal import Decimal

from pydantic import BaseModel, Field

from app.modules.cart.service import CartItemView, CartView


class AddItemRequest(BaseModel):
    book_id: uuid.UUID
    quantity: int = Field(gt=0)


class UpdateItemRequest(BaseModel):
    quantity: int = Field(gt=0)


class CartItemOut(BaseModel):
    book_id: str
    title: str
    author_name: str
    unit_price: Decimal
    quantity: int
    line_total: Decimal

    @classmethod
    def from_view(cls, item: CartItemView) -> "CartItemOut":
        return cls(
            book_id=item.book_id,
            title=item.title,
            author_name=item.author_name,
            unit_price=item.unit_price,
            quantity=item.quantity,
            line_total=item.line_total,
        )


class CartOut(BaseModel):
    items: list[CartItemOut]
    total: Decimal

    @classmethod
    def from_view(cls, cart: CartView) -> "CartOut":
        return cls(items=[CartItemOut.from_view(i) for i in cart.items], total=cart.total)
