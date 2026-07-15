"""Service-to-service auth for Inventory's write endpoints (SDD 7.3: POST /reserve
and POST /release require an "internal token"). Replaces the Stage 1 stand-in
(any authenticated customer JWT) now that a real caller - Order - exists.
"""

import hmac

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


def require_internal_token(x_internal_token: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if x_internal_token is None or not hmac.compare_digest(
        x_internal_token, settings.internal_service_token
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid internal service token"
        )
