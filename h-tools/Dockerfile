# Conteneur d'un tool. scripts/deploy_tool.sh assemble le contexte : ce Dockerfile, railway.json, pyproject.toml,
# uv.lock, h_tools/ et tools/<nom>/ copié en tool/. Devin n'écrit jamais de Dockerfile.
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
RUN uv run --no-sync playwright install --with-deps chromium
COPY h_tools ./h_tools
COPY tool ./tool
RUN if [ -f tool/requirements.txt ]; then uv pip install -r tool/requirements.txt; fi
ENV TOOL_DIR=/app/tool
# « :: » écoute en IPv4 et IPv6, comme le demande le réseau privé Railway
CMD ["sh", "-c", "uv run --no-sync uvicorn --factory h_tools.server:create_app --host :: --port ${PORT:-8080}"]
