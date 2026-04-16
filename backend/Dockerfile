FROM python:3.11-slim

WORKDIR /app

# System deps for psycopg (PostgreSQL client)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
ARG PIP_INDEX_URL=https://pypi.org/simple
ARG PIP_TRUSTED_HOST=
RUN if [ -n "$PIP_TRUSTED_HOST" ]; then \
      pip install --no-cache-dir -i "$PIP_INDEX_URL" --trusted-host "$PIP_TRUSTED_HOST" -r requirements.txt; \
    else \
      pip install --no-cache-dir -i "$PIP_INDEX_URL" -r requirements.txt; \
    fi

COPY . .

# Create upload dir (used when STORAGE_BACKEND=local as fallback)
RUN mkdir -p /app/data/uploads

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
