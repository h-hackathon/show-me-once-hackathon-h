# Image du site web Comptarex (Railway la construit toute seule : dossier racine du service = comptarex/).
# L'application de bureau (PySide6) n'est pas installée ici.
FROM python:3.12-slim

RUN pip install --no-cache-dir "uv>=0.9"
WORKDIR /app
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 PATH="/app/.venv/bin:$PATH" COMPTAREX_PROD=1 PORT=8042

COPY pyproject.toml uv.lock README.md .python-version ./
RUN uv sync --locked --no-dev --no-install-project
COPY comptarex ./comptarex
COPY data ./data
RUN uv sync --locked --no-dev

# Un seul processus (SQLite), plusieurs fils. Railway fournit $PORT. --preload : le contrôle des secrets
# tourne dans le processus maître, qui s'arrête net au lieu de relancer le worker en boucle.
CMD ["sh", "-c", "exec gunicorn --preload --workers 1 --threads 8 --bind 0.0.0.0:${PORT} --access-logfile - comptarex.web.app:app"]
