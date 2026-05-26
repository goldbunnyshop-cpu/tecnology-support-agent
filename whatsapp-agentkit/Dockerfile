FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for PostgreSQL (asyncpg) and build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

# Copy and install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment
ENV PORT=8080
EXPOSE 8080

# Run application
CMD ["uvicorn", "agent.main:app", "--host", "0.0.0.0", "--port", "8080"]
