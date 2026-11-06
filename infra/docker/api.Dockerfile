# Build context: repository root.
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /usr/local/bin/uv
WORKDIR /app

COPY apps/api/pyproject.toml apps/api/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY apps/api/ ./
RUN uv sync --frozen --no-dev \
 && useradd --create-home --uid 10001 app \
 && mkdir -p /app/var/media && chown -R app /app/var
USER app
ENV PATH="/app/.venv/bin:$PATH" ENV=production PORT=8000
EXPOSE 8000
CMD ["python", "-m", "app.serve"]
