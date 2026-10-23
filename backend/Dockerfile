# Backend image: FastAPI on uvicorn. Migrations + (optional) seed run at container start so a
# fresh Render/Railway deploy comes up with the dataset already loaded.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

EXPOSE 8000
CMD ["sh", "-c", "uv run alembic upgrade head && (if [ \"$SEED_ON_START\" = \"true\" ]; then uv run python -m scripts.seed; fi) && uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
