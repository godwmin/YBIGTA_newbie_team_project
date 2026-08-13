FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY mcp_server/requirements.txt ./mcp_server/requirements.txt
RUN pip install --no-cache-dir -r mcp_server/requirements.txt \
    && useradd --create-home --uid 10001 appuser

COPY --chown=appuser:appuser mcp_server/ ./mcp_server/

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"

CMD ["python", "-m", "mcp_server.server"]
