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
# « :: » écoute en IPv4 et IPv6, comme le demande le réseau privé Railway
CMD ["sh", "-c", "uvicorn --factory h_tools.server:create_app --host :: --port ${PORT:-8080}"]
