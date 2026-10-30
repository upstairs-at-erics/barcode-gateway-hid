# Smallest practical image: Alpine Python + Flask, no compiler in the final layer.
# Multi-arch: linux/amd64 (Intel/AMD), linux/arm64 (Pi 5 and 64-bit Pi 3B),
# linux/arm/v7 (32-bit Pi 3B). See docker-compose.yml for buildx.
#
#   docker buildx build --platform linux/amd64,linux/arm64,linux/arm/v7 \
#     -t barcode-gateway:1.0 --load .
#   (--load is one platform at a time; use --push for all three at once.)

FROM python:3.11-alpine AS wheels
RUN apk add --no-cache gcc musl-dev
RUN pip install --no-cache-dir --prefix=/out Flask==2.2.2 Werkzeug==2.2.2 \
    && find /out -type d -name __pycache__ -exec rm -rf {} + \
    && find /out -type f -name '*.pyc' -delete

FROM python:3.11-alpine
COPY --from=wheels /out /usr/local
WORKDIR /app
COPY app.py config.py reader.py sender.py store.py ./
COPY templates ./templates
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 BIND=0.0.0.0 PORT=8095
EXPOSE 8095
CMD ["python3", "/app/app.py"]
