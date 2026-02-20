# syntax=docker/dockerfile:1.6

FROM python:3.11-slim

# Get uv (recommended: copy the standalone binary from Astral's image)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LOG_LEVEL=INFO \
    UV_LINK_MODE=copy

# psycopg (via langgraph-checkpoint-postgres) needs libpq at runtime
RUN apt-get update \
 && apt-get install -y --no-install-recommends libpq5 \
 && rm -rf /var/lib/apt/lists/*

# --- Dependency layer (cached) ---
# Copy only the lockfile + pyproject first
COPY apps/assistant-backend/pyproject.toml apps/assistant-backend/uv.lock ./

# Install only dependencies (not your project code yet) for better caching
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-dev

# --- App layer ---
COPY apps/assistant-backend/app ./app

# Now install the project itself into the same venv
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

# Use the venv automatically
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

