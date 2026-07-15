from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import create_access_token, get_current_user_id
from app.modules.identity import service
from app.modules.identity.schemas import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserProfile,
)

router = APIRouter(prefix="/api/auth", tags=["identity"])


@router.post("/register", response_model=UserProfile, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> UserProfile:
    try:
        user = service.register(
            db,
            email=payload.email,
            password=payload.password,
            display_name=payload.display_name,
        )
    except service.DuplicateEmailError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        ) from exc
    return UserProfile.model_validate(user)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        user = service.authenticate(db, email=payload.email, password=payload.password)
    except service.InvalidCredentialsError as exc:
        # Generic message regardless of whether the email or the password was wrong (FR-ID-03).
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        ) from exc
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.get("/me", response_model=UserProfile)
def get_me(
    db: Session = Depends(get_db), current_user_id: str = Depends(get_current_user_id)
) -> UserProfile:
    user = service.get_profile(db, current_user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    return UserProfile.model_validate(user)


@router.get("/health/ready")
def health_ready(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable"
        ) from exc
    return {"status": "ready"}
