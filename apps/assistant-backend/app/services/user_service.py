import logging

from app.api.schemas.auth import UserResponse
from app.services.contracts import DatabaseServiceProtocol

logger = logging.getLogger(__name__)


class UserService:
    """User identity and credential operations."""

    def __init__(self, database: DatabaseServiceProtocol) -> None:
        self._database = database

    async def get_user_by_email(self, email: str) -> dict[str, str] | None:
        row = await self._database.fetchrow(
            """
            SELECT u.id::text AS id, u.name, u.email, i.provider_subject, i.password_hash
            FROM users u
            JOIN identities i ON i.user_id = u.id
            WHERE u.email = $1 AND i.provider = 'local'
            """,
            email,
        )
        if row is None:
            logger.debug("user lookup by email returned no rows")
            return None

        return {
            "id": row["id"],
            "name": row["name"],
            "email": row["email"],
            "provider_subject": row["provider_subject"],
            "password_hash": row["password_hash"],
        }

    async def get_user(self, user_id: str) -> UserResponse | None:
        row = await self._database.fetchrow(
            "SELECT id::text AS id, name, email FROM users WHERE id = $1::uuid",
            user_id,
        )
        if row is None:
            logger.debug("user lookup by id returned no rows", extra={"user_id": user_id})
            return None
        return UserResponse(id=row["id"], name=row["name"], email=row["email"])
