FROM ghcr.io/astral-sh/uv:0.10.3 AS uv
FROM python:3.13.3-slim
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1
WORKDIR /app
COPY services/backend/pyproject.toml services/backend/uv.lock services/backend/.python-version ./services/backend/
RUN uv sync --project services/backend --locked --no-dev --no-install-project
COPY services/backend/src ./services/backend/src
RUN uv sync --project services/backend --locked --no-dev && useradd --uid 10001 --create-home cce
USER cce
EXPOSE 8000
CMD ["/app/services/backend/.venv/bin/uvicorn", "cce.api_entrypoint:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
