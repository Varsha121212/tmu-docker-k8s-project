"""Identity's business logic. Callers outside this service reach it only over
HTTP (POST /register, POST /login, GET /me) per SDD 7.1 - this file's
signatures are the same public boundary the monolith module used, now enforced
by the process boundary instead of import-linter.
"""

import uuid

from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.modules.identity.internal import repository
from app.modules.identity.internal.models import User


class DuplicateEmailError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


def register(db: Session, *, email: str, password: str, display_name: str) -> User:
    if repository.get_by_email(db, email) is not None:
        raise DuplicateEmailError(email)
    return repository.create(
        db, email=email, password_hash=hash_password(password), display_name=display_name
    )


def authenticate(db: Session, *, email: str, password: str) -> User:
    user = repository.get_by_email(db, email)
    if user is None or not user.active or not verify_password(password, user.password_hash):
        # Deliberately identical error for "no such user" and "wrong password" (FR-ID-03).
        raise InvalidCredentialsError()
    return user


def get_profile(db: Session, user_id: str) -> User | None:
    try:
        parsed_id = uuid.UUID(user_id)
    except ValueError:
        return None
    return repository.get_by_id(db, parsed_id)
