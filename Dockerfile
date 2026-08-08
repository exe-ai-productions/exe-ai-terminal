# Exe AI Terminal — image for everyone who wants to run it themselves.
#
# Two stages: the first builds the dependencies, the second takes only the
# finished result along. That keeps the image small and leaves no build
# tools behind in production.

# First stage: build the frontend. Node is only needed here and does not
# end up in the finished image.
FROM node:22-slim AS oberflaeche

WORKDIR /oberflaeche
COPY frontend/package*.json ./
RUN npm ci --no-fund --no-audit
COPY frontend/ ./
# Vite writes to ../static/app — so the directory has to exist.
RUN mkdir -p /static/app && npm run build -- --outDir /static/app --emptyOutDir


FROM python:3.12-slim AS bau

WORKDIR /bau
COPY requirements.txt .
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt


FROM python:3.12-slim

# Do not run as root.
RUN useradd --create-home --uid 1000 exeai

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY --from=bau /opt/venv /opt/venv

WORKDIR /app
COPY --chown=exeai:exeai app ./app
COPY --chown=exeai:exeai mcp ./mcp
COPY --chown=exeai:exeai static ./static
# Lay the built frontend from the first stage on top.
COPY --from=oberflaeche --chown=exeai:exeai /static/app ./static/app
COPY --chown=exeai:exeai config.yaml mcp_servers.json ./

# Database, uploads, and logs live here — mount as a volume,
# otherwise they are gone on the next start.
RUN mkdir -p /app/data /app/logs && chown -R exeai:exeai /app/data /app/logs
VOLUME ["/app/data", "/app/logs"]

USER exeai
EXPOSE 8090

# Checks its own health endpoint — without curl, which is not in the image.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8090/health', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8090"]
