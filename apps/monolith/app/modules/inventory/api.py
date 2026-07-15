import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user_id
from app.modules.inventory import service
from app.modules.inventory.schemas import ReleaseRequest, ReservationOut, ReserveRequest, StockOut

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


@router.get("/health/ready")
def health_ready(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable"
        ) from exc
    return {"status": "ready"}


@router.get("/stock/{book_id}", response_model=StockOut)
def get_stock(book_id: uuid.UUID, db: Session = Depends(get_db)) -> StockOut:
    available_qty, version = service.get_available_quantity(db, book_id)
    return StockOut(book_id=book_id, available_qty=available_qty, version=version)


@router.post("/reserve", response_model=ReservationOut, status_code=status.HTTP_201_CREATED)
def reserve(
    payload: ReserveRequest,
    db: Session = Depends(get_db),
    # SDD 7.3: "Internal token" - no service-to-service auth exists yet in the Stage 1
    # monolith, so JWT-authenticated caller is the stand-in, same pattern as Catalog's
    # POST /books. Real internal-service auth arrives with the Stage 2/3 network design.
    _current_user_id: str = Depends(get_current_user_id),
) -> ReservationOut:
    try:
        reservation = service.reserve(
            db,
            book_id=payload.book_id,
            quantity=payload.quantity,
            idempotency_key=payload.idempotency_key,
        )
    except service.InsufficientStockError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Insufficient stock"
        ) from exc
    return ReservationOut.model_validate(reservation)


@router.post("/release", response_model=ReservationOut)
def release(
    payload: ReleaseRequest,
    db: Session = Depends(get_db),
    _current_user_id: str = Depends(get_current_user_id),
) -> ReservationOut:
    try:
        reservation = service.release(db, payload.reservation_id)
    except service.ReservationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Reservation not found"
        ) from exc
    return ReservationOut.model_validate(reservation)
