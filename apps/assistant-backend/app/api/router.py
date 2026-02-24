from fastapi import APIRouter

from app.api.routers.auth import router as auth_router
from app.api.routers.chat import router as chat_router
from app.api.routers.journal import router as journal_router
from app.api.routers.knowledge import router as knowledge_router
from app.api.routers.users import router as users_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(chat_router)
api_router.include_router(knowledge_router)
api_router.include_router(journal_router)
api_router.include_router(users_router)
