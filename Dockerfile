# syntax=docker/dockerfile:1
FROM python:3.15-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# Dependencies first, so code changes don't invalidate the dependency layer.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-dev --no-install-project
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --no-editable

FROM python:3.15-slim
# pip isn't needed at runtime, and its bundled libraries are a recurring source of CVEs.
RUN python -m pip uninstall --yes --quiet pip \
    && useradd --system --uid 10001 --no-create-home app
COPY --from=build --chown=app:app /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    STARTER_APP_HOST=0.0.0.0 \
    STARTER_APP_ENVIRONMENT=production
# begin: sqlite-only
# The database file lives on a volume; mount durable storage at /data.
RUN mkdir /data && chown app:app /data
ENV STARTER_APP_DATABASE_URL=sqlite:////data/starter_app.db
VOLUME /data
# end: sqlite-only
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"]
# Run migrations as a separate one-off step before rolling out: `app db migrate`.
CMD ["app", "serve"]
