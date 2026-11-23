FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 RPD_STATE_DIR=/data/state RPD_DATA_PATH=/data/current.enc.json
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home --uid 10001 rpd && mkdir /data && chown rpd:rpd /data
COPY backend ./backend
COPY index.html app.js command-center.js styles.css command-center.css ./
USER rpd
EXPOSE 8765
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8765", "--workers", "1", "--no-access-log", "--proxy-headers", "--forwarded-allow-ips", "127.0.0.1"]
