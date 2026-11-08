# Conteneur d'un tool. scripts/deploy_tool.sh assemble le contexte : ce Dockerfile, railway.json, pyproject.toml,
# uv.lock, h_tools/ et tools/<nom>/ copié en tool/. Devin n'écrit jamais de Dockerfile.
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /usr/local/bin/uv
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
RUN uv run --no-sync playwright install --with-deps chromium
COPY h_tools ./h_tools
COPY tool ./tool
RUN if [ -f tool/requirements.txt ]; then uv pip install -r tool/requirements.txt; fi
RUN useradd --create-home --uid 10001 tool
USER tool
# Sans SMO_SERVER_TOKEN, le conteneur refuse tout appel (h_tools/server.py) : jamais public par erreur.
ENV TOOL_DIR=/app/tool SMO_AUTH_REQUIRED=1 PATH=/app/.venv/bin:$PATH
# 0.0.0.0 (IPv4) : le proxy public de Railway arrive en IPv4. Uvicorn sur « :: » n'écoute qu'en IPv6 (asyncio pose
# IPV6_V6ONLY) : le tool répondait 502. SMO est dans un autre projet et passe par l'adresse publique.
CMD ["sh", "-c", "uvicorn --factory h_tools.server:create_app --host 0.0.0.0 --port ${PORT:-8080}"]
