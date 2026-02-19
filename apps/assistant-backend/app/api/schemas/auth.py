from typing import Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str = Field(..., description="Email address for a locally managed assistant account")
    password: str = Field(..., min_length=8, description="Plain-text password used for local login")
    session_mode: Literal["web", "api"] = Field(
        default="web",
        description="Target client mode: browser session cookie flow (`web`) or token flow (`api`)",
    )
    issuance_policy: Literal["session", "tokens"] = Field(
        default="session",
        description="Token issuance strategy for successful login",
    )


class TokenPairResponse(BaseModel):
    access_token: str = Field(..., description="Short-lived JWT access token")
    refresh_token: str = Field(..., description="Long-lived opaque refresh token")
    token_type: str = Field(default="bearer", description="Authorization scheme used by access_token")
    expires_in: int = Field(..., description="Access token expiration in seconds")


class TokenRefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=16, description="Previously issued refresh token")


class SessionResponse(BaseModel):
    session_established: bool = Field(..., description="Whether a cookie-backed session was established")
    user_name: str = Field(..., description="Display name of the authenticated user")


class UnifiedPrincipal(BaseModel):
    user_id: str = Field(..., description="Canonical user UUID as string")
    email: str = Field(..., description="User email associated with the principal")
    display_name: str = Field(..., description="User-facing display name")


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
