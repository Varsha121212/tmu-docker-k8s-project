"""Redis-backed cart storage (SDD 8.3: cart:{user_id} hash of book_id -> quantity)."""

import redis


def _key(user_id: str) -> str:
    return f"cart:{user_id}"


def get_items(client: redis.Redis, user_id: str) -> dict[str, int]:
    raw = client.hgetall(_key(user_id))
    return {book_id: int(qty) for book_id, qty in raw.items()}


def set_item(client: redis.Redis, user_id: str, book_id: str, quantity: int) -> None:
    client.hset(_key(user_id), book_id, quantity)


def item_exists(client: redis.Redis, user_id: str, book_id: str) -> bool:
    return bool(client.hexists(_key(user_id), book_id))


def remove_item(client: redis.Redis, user_id: str, book_id: str) -> bool:
    removed = client.hdel(_key(user_id), book_id)
    return bool(removed)


def clear(client: redis.Redis, user_id: str) -> None:
    client.delete(_key(user_id))
