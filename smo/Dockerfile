# Serveur SMO (Railway) : worker des custom tools H + tools compilés (Playwright/Chromium).
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /usr/local/bin/uv
WORKDIR /app
# evdev (dépendance Linux de l'extra « desktop » de hai-agents) n'existe qu'en sources : il faut un compilateur C.
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev linux-libc-dev \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
RUN .venv/bin/playwright install --with-deps chromium   # pas « uv run » : le code du projet n'est pas encore copié
COPY . .
RUN uv sync --frozen --no-dev
CMD ["sh", "-c", "uv run smo serve --port ${PORT:-8000}"]
