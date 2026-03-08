from __future__ import annotations

from typing import Literal

from app.contracts.base import StrictModel


class HealthResponse(StrictModel):
    status: Literal["ok"]
