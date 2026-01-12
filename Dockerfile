# Backend Dockerfile for Cloud Run
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY web/backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY web/backend /app/web/backend
COPY service-account-key.json /app/service-account-key.json

ENV GOOGLE_APPLICATION_CREDENTIALS=/app/service-account-key.json
ENV PORT=8080

EXPOSE 8080

CMD ["uvicorn", "web.backend.app:app", "--host", "0.0.0.0", "--port", "8080"]
