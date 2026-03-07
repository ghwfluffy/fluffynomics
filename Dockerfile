FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY ./python/requirements.txt .
RUN \
    pip install --no-cache-dir -r requirements.txt && \
    rm -f requirements.txt

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
