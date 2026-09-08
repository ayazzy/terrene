FROM python:3.14-slim
WORKDIR /app
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend /app/backend
ENV CRC_ENV=production
CMD ["sh", "-c", "python -m backend.migrate && uvicorn backend.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
