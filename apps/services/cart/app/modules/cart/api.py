import redis
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.redis import get_redis
from app.core.security import get_current_user_id
from app.modules.cart import service
from app.modules.cart.schemas import AddItemRequest, CartOut, UpdateItemRequest

router = APIRouter(prefix="/api/cart", tags=["cart"])


@router.get("/health/ready")
def health_ready(redis_client: redis.Redis = Depends(get_redis)) -> dict:
    try:
        redis_client.ping()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Redis unavailable"
        ) from exc
    return {"status": "ready"}


@router.get("", response_model=CartOut)
def get_cart(
    redis_client: redis.Redis = Depends(get_redis),
    current_user_id: str = Depends(get_current_user_id),
) -> CartOut:
    cart = service.get_cart(redis_client, user_id=current_user_id)
    return CartOut.from_view(cart)


@router.post("/items", response_model=CartOut, status_code=status.HTTP_201_CREATED)
def add_item(
    payload: AddItemRequest,
    redis_client: redis.Redis = Depends(get_redis),
    current_user_id: str = Depends(get_current_user_id),
) -> CartOut:
    try:
        service.add_item(
            redis_client,
            user_id=current_user_id,
            book_id=str(payload.book_id),
            quantity=payload.quantity,
        )
    except service.BookNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found") from exc
    cart = service.get_cart(redis_client, user_id=current_user_id)
    return CartOut.from_view(cart)


@router.patch("/items/{book_id}", response_model=CartOut)
def update_item(
    book_id: str,
    payload: UpdateItemRequest,
    redis_client: redis.Redis = Depends(get_redis),
    current_user_id: str = Depends(get_current_user_id),
) -> CartOut:
    try:
        service.update_item(
            redis_client, user_id=current_user_id, book_id=book_id, quantity=payload.quantity
        )
    except service.ItemNotInCartError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Item not in cart"
        ) from exc
    cart = service.get_cart(redis_client, user_id=current_user_id)
    return CartOut.from_view(cart)


@router.delete("/items/{book_id}", response_model=CartOut)
def remove_item(
    book_id: str,
    redis_client: redis.Redis = Depends(get_redis),
    current_user_id: str = Depends(get_current_user_id),
) -> CartOut:
    try:
        service.remove_item(redis_client, user_id=current_user_id, book_id=book_id)
    except service.ItemNotInCartError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Item not in cart"
        ) from exc
    cart = service.get_cart(redis_client, user_id=current_user_id)
    return CartOut.from_view(cart)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def clear_cart(
    redis_client: redis.Redis = Depends(get_redis),
    current_user_id: str = Depends(get_current_user_id),
) -> None:
    # SDD 7.4: "Internal call after successful order." Order forwards the customer's
    # own JWT when calling this route internally (Cart has no separate internal-token
    # surface - its routes are already customer-scoped by that same token).
    service.clear_cart(redis_client, user_id=current_user_id)
