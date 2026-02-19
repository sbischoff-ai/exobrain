from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI

from app.api.router import api_router
from app.api.routers.health import router as health_router
from app.core.logging import configure_logging
from app.core.settings import get_settings
from app.services.auth_service import AuthService
from app.services.database_service import DatabaseService
from app.services.session_store import RedisSessionStore
from app.services.journal_service import JournalService
from app.services.user_service import UserService

settings = get_settings()
configure_logging(settings.effective_log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("starting assistant backend", extra={"app_env": settings.app_env})

    database_service = DatabaseService(
        dsn=settings.assistant_db_dsn,
        reshape_schema_query=settings.reshape_schema_query,
    )
    await database_service.connect()
    logger.info("database connection pool initialized")

    user_service = UserService(database=database_service)
    session_store = RedisSessionStore(
        redis_url=settings.assistant_cache_redis_url,
        key_prefix=settings.assistant_cache_key_prefix,
    )
    await session_store.ping()
    logger.info("assistant cache connection initialized")
    auth_service = AuthService(settings=settings, user_service=user_service, session_store=session_store)
    journal_service = JournalService(database=database_service)

    app.state.settings = settings
    app.state.database_service = database_service
    app.state.user_service = user_service
    app.state.auth_service = auth_service
    app.state.session_store = session_store
    app.state.journal_service = journal_service

    try:
        yield
    finally:
        await session_store.close()
        await database_service.disconnect()
        logger.info("assistant backend shutdown complete")


app = FastAPI(
    title="Exobrain Assistant Backend",
    version="0.1.0",
    docs_url="/docs" if settings.enable_swagger else None,
    redoc_url="/redoc" if settings.enable_swagger else None,
    openapi_url="/openapi.json" if settings.enable_swagger else None,
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(api_router, prefix="/api")
