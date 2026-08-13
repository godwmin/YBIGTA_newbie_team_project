FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY collector/requirements.txt ./collector/requirements.txt
RUN pip install --no-cache-dir -r collector/requirements.txt \
    && useradd --create-home --uid 10001 collector

COPY --chown=collector:collector collector/ ./collector/

USER collector
CMD ["python", "-m", "collector.main"]
