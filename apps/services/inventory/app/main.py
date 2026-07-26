import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.modules.inventory.api import router as inventory_router

app = FastAPI(title="Online Bookstore - Inventory Service")

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

app.include_router(inventory_router)

Instrumentator(excluded_handlers=["/health/live", ".*/health/ready$"]).instrument(app).expose(
    app, endpoint="/metrics", include_in_schema=False
)


@app.get("/health/live")
def health_live() -> dict:
    return {"status": "live"}
