# Serveur SMO (Railway) : worker des custom tools H + tools compilés (Playwright/Chromium).
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
RUN uv run playwright install --with-deps chromium
COPY . .
RUN uv sync --frozen --no-dev
CMD ["sh", "-c", "uv run smo serve --port ${PORT:-8000}"]
