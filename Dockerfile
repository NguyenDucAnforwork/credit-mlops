FROM python:3.12-slim

WORKDIR /app

# Install build dependencies for psycopg2 / scipy + curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first (cached layer — only re-installs on lockfile change)
COPY pyproject.toml uv.lock ./

# Install production deps only (no venv, no project src)
RUN uv sync --frozen --no-dev --no-install-project

# Put the venv on PATH so plain `uvicorn` works in CMD
ENV PATH="/app/.venv/bin:$PATH"

# Copy application code
COPY src/ ./src/
COPY api/ ./api/
COPY artifacts/ ./artifacts/
COPY data/processed/ ./data/processed/
COPY .env .

WORKDIR /app/api

ENV PYTHONPATH=/app/src:/app/api
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
