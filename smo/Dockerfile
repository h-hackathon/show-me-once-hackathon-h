# Serveur SMO (Railway) : page d'enregistrement, worker des custom tools H, relais vers h-tools (Playwright/Chromium).
# Sans l'option desktop de hai-agents : sous Linux elle tire evdev (sources seules, il faudrait gcc), et le serveur
# n'en a pas besoin (l'agent bureau travaille dans l'environnement desktop configuré dans H).
FROM python:3.12-slim
RUN pip install --no-cache-dir uv==0.13.1   # via PyPI : ghcr.io est parfois injoignable depuis Railway
ENV PYTHONUNBUFFERED=1 UV_LINK_MODE=copy
WORKDIR /app

# Dépendances d'abord (couche en cache tant que pyproject.toml et uv.lock ne changent pas)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
RUN .venv/bin/playwright install --with-deps chromium   # pas « uv run » : le code du projet n'est pas encore copié

# Puis le code
COPY . .
RUN uv sync --frozen --no-dev

# Railway donne le port dans $PORT
CMD ["sh", "-c", ".venv/bin/smo serve --host 0.0.0.0 --port ${PORT:-8000}"]
