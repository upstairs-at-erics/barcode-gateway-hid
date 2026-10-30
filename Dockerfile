# Barcode Gateway runtime image. Code is NOT baked in: /srv/barcode is bind-mounted at /app.
FROM python:3.11.14-slim-bookworm
RUN pip install --no-cache-dir Flask==2.2.2 Werkzeug==2.2.2
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 BIND=0.0.0.0 PORT=8095
WORKDIR /app
CMD ["python3", "/app/app.py"]
