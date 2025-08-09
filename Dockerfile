# syntax=docker/dockerfile:1.6

# Use a Python image with uv pre-installed
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS base

# Set working directory
WORKDIR /app

# System deps required to build psycopg2 from source (pg_config)
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Recommended envs for Python in containers
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    UV_LINK_MODE=copy

# Copy dependency manifests first (better layer caching)
COPY pyproject.toml uv.lock ./

# Install project dependencies (no dev, respect lockfile)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# Copy the rest of the application
COPY . .

# Expose the port used by the server
EXPOSE 8000

# Run DB migrations then start the server
CMD ["/bin/sh", "-lc", "uv run alembic upgrade head && uv run server.py"]
