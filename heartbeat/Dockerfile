# Base image is cached in ACR to avoid Docker Hub rate limits
ARG ACR_LOGIN_SERVER
FROM ${ACR_LOGIN_SERVER}/python:3.11-slim

LABEL description="CDC pipeline heartbeat — keeps Event Hubs connections alive"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY heartbeat.py .

# Run as non-root
RUN useradd -r heartbeat
USER heartbeat

CMD ["python", "-u", "heartbeat.py"]
