FROM python:3.11-slim

WORKDIR /app

# Install apt dependencies
RUN \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        gzip \
        postgresql-client \
        && \
    rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY ./python/requirements.txt /tmp/requirements.txt
RUN \
    pip install --no-cache-dir -r /tmp/requirements.txt && \
    rm -f /tmp/requirements.txt

COPY ./python/ /app/

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
