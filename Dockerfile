# syntax=docker/dockerfile:1

# --- build -----------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Dependencies first, so this layer is cached until the lockfile changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --no-dev

COPY src ./src
COPY prompts ./prompts
COPY alembic ./alembic
COPY alembic.ini ./
COPY docker-entrypoint.sh ./
RUN uv sync --locked --no-dev

# --- runtime ---------------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime

# Never run as root: a compromised process should not own the container.
RUN useradd --create-home --uid 10001 appuser

WORKDIR /app
COPY --from=builder --chown=appuser:appuser /app /app

# Prompts live outside the package, so the path is stated rather than guessed.
# The loader also searches, but being explicit removes the ambiguity.
ENV PATH="/app/.venv/bin:$PATH" \
    TALENTFLOW_PROMPTS_DIR=/app/prompts \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER appuser
EXPOSE 8000

# Uses the standard library rather than curl, which slim images do not carry.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"

# Migrations run before the server starts; see the entrypoint for why.
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "talentflow.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
