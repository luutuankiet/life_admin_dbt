# One image for both services (dagster, listener). Build context: EL/ticktick/ingest.
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app
# Dependencies first (cached layer), straight from the committed lock file.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
RUN uv sync --locked --no-dev

ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    DAGSTER_HOME=/opt/dagster \
    INGEST_STATE_DIR=/state
COPY docker/dagster.yaml /opt/dagster/dagster.yaml

EXPOSE 3000
CMD ["dagster", "dev", "-m", "ticktick_ingest.defs", "-h", "0.0.0.0", "-p", "3000"]
