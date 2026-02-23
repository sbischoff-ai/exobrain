from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI

from app.agents.factory import build_main_agent
from app.api.router import api_router
from app.api.routers.health import router as health_router
from app.core.logging import configure_logging
from app.core.settings import get_settings
from app.dependency_injection import build_container, register_chat_agent
from app.services.contracts import DatabaseServiceProtocol, JournalCacheProtocol, SessionStoreProtocol

settings = get_settings()
configure_logging(settings.effective_log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("starting assistant backend", extra={"app_env": settings.app_env})

    container = build_container(settings)

    database_service = container.resolve(DatabaseServiceProtocol)
    await database_service.connect()
    logger.info("database connection pool initialized")

    session_store = container.resolve(SessionStoreProtocol)
    await session_store.ping()

    journal_cache = container.resolve(JournalCacheProtocol)
    await journal_cache.ping()
    logger.info("assistant cache connection initialized")

    main_agent = await build_main_agent(settings)
    register_chat_agent(container, main_agent)

    app.state.container = container

    try:
        yield
    finally:
        if hasattr(main_agent, "aclose"):
            await main_agent.aclose()
        await journal_cache.close()
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
