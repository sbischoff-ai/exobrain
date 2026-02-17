from app.api.schemas.auth import UserResponse
from app.services.database_service import DatabaseService


class UserService:
    """User identity and credential operations."""

    def __init__(self, database: DatabaseService) -> None:
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
            return None
        return UserResponse(id=row["id"], name=row["name"], email=row["email"])
