# syntax=docker/dockerfile:1
FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (layer cache friendly)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# No port needed — this is a background worker, not a web server
ENV PYTHONUNBUFFERED=1

CMD ["python", "worker.py"]
