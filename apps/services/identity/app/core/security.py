import threading
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings

_hasher = PasswordHasher()
_bearer_scheme = HTTPBearer(auto_error=False)

# Found via a real OOMKill crash-loop during US-PLT-22's Stage 3 load test:
# argon2-cffi's default memory_cost is 65536 KiB (64 MiB) *per hash call*,
# and FastAPI runs this sync function in a background thread pool with no
# concurrency cap of its own - enough simultaneous login/register requests
# can drive memory need arbitrarily high (a resource-exhaustion risk any
# client could trigger, not just a load-test artifact). Bounding concurrent
# hashing to 4 keeps worst-case hashing memory at ~256 MiB, comfortably
# under the container's 512Mi limit alongside the base process footprint.
_hash_concurrency = threading.Semaphore(4)


def hash_password(plain_password: str) -> str:
    with _hash_concurrency:
        return _hasher.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        with _hash_concurrency:
            return _hasher.verify(password_hash, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def create_access_token(subject: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


class InvalidTokenError(Exception):
    pass


def decode_access_token(token: str) -> str:
    """Returns the subject (user id) claim, or raises InvalidTokenError."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc

    subject = payload.get("sub")
    if not subject:
        raise InvalidTokenError("token missing subject claim")
    return subject


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> str:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return decode_access_token(credentials.credentials)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
