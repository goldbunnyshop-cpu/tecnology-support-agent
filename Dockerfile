FROM python:3.11-slim
WORKDIR /app
ENV PYTHONPATH=/app:$PYTHONPATH
ENV PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir "asyncpg>=0.29.0" && \
    pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
# Bind al puerto que Railway inyecta en $PORT (cae a 8000 en local).
# Forma shell para que ${PORT} se expanda. Si se hardcodea --port 8000 y
# Railway asigna otro puerto, el proxy no encuentra la app → 502.
CMD ["sh", "-c", "uvicorn agent.main:app --host 0.0.0.0 --port ${PORT:-8000}"]