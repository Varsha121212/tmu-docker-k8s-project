import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class StockOut(BaseModel):
    book_id: uuid.UUID
    available_qty: int
    version: int


class ReserveRequest(BaseModel):
    book_id: uuid.UUID
    quantity: int = Field(gt=0)
    idempotency_key: str = Field(min_length=1, max_length=200)


class ReleaseRequest(BaseModel):
    reservation_id: uuid.UUID


class ReservationOut(BaseModel):
    id: uuid.UUID
    book_id: uuid.UUID
    quantity: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
