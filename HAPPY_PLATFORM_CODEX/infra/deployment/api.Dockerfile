FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client && rm -rf /var/lib/apt/lists/*
COPY apps/api /app/apps/api
COPY database /app/database
COPY scripts/api.py scripts/preflight.py /app/scripts/
COPY VERSION /app/VERSION
ENV HAPPY_RELEASE_VERSION=1.0.0-rc.1
RUN pip install --no-cache-dir /app/apps/api && useradd --uid 10001 --create-home happy
WORKDIR /app/apps/api
USER happy
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --no-access-log"]
