from fastapi import FastAPI

from app.api.router import api_router
from app.core.settings import get_settings

settings = get_settings()

app = FastAPI(
    title="Exobrain Assistant Backend",
    version="0.1.0",
    docs_url="/docs" if settings.enable_swagger else None,
    redoc_url="/redoc" if settings.enable_swagger else None,
    openapi_url="/openapi.json" if settings.enable_swagger else None,
)

app.include_router(api_router, prefix="/api")
