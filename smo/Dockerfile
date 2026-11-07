# Serveur SMO (Railway) : page d'enregistrement, worker des custom tools H, tools compilés (Playwright/Chromium).
# Sans l'option desktop : sous Linux elle tire evdev (à compiler), et le serveur en ligne ne pilote aucun bureau.
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /usr/local/bin/uv
ENV PYTHONUNBUFFERED=1 UV_LINK_MODE=copy
WORKDIR /app

# Dépendances d'abord (couche en cache tant que pyproject.toml et uv.lock ne changent pas)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
RUN .venv/bin/playwright install --with-deps chromium

# Puis le code
COPY . .
RUN uv sync --frozen --no-dev

# Railway donne le port dans $PORT
CMD ["sh", "-c", ".venv/bin/smo serve --host 0.0.0.0 --port ${PORT:-8000}"]
