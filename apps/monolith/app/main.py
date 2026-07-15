import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.modules.cart.api import router as cart_router
from app.modules.catalog.api import router as catalog_router
from app.modules.identity.api import router as identity_router
from app.modules.inventory.api import router as inventory_router
from app.modules.order.api import router as order_router

app = FastAPI(title="Online Bookstore - Monolith (Stage 1)")

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-Id", str(uuid.uuid4()))
    request.state.correlation_id = correlation_id
    response = await call_next(request)
    response.headers["X-Correlation-Id"] = correlation_id
    return response


register_exception_handlers(app)

app.include_router(identity_router)
app.include_router(catalog_router)
app.include_router(inventory_router)
app.include_router(cart_router)
app.include_router(order_router)


@app.get("/health/live")
def health_live() -> dict:
    return {"status": "live"}
