FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir "asyncpg>=0.29.0" && \
    pip install --no-cache-dir -r requirements.txt
RUN python -m playwright install chromium && \
    python -m playwright install-deps chromium
COPY . .
EXPOSE 8000
CMD uvicorn agent.main:app --host 0.0.0.0 --port ${PORT:-8000}