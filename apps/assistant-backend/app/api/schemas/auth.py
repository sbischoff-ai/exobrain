from typing import Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    password: str = Field(..., min_length=8)
    session_mode: Literal["web", "api"] = "web"
    issuance_policy: Literal["session", "tokens"] = "session"


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class SessionResponse(BaseModel):
    session_established: bool
    user_name: str


class UnifiedPrincipal(BaseModel):
    user_id: str
    email: str
    display_name: str


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
