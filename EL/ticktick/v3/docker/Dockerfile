FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:0.8.15 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY poller /app/poller
COPY config /app/config

RUN uv pip install --system .

RUN mkdir -p /app/data/raw_batches

EXPOSE 8000

CMD ["ticktick-v3-poller", "serve-webapp", "--host", "0.0.0.0", "--port", "8000"]