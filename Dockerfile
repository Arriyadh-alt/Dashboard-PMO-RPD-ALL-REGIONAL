FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 RPD_STATE_DIR=/data/state RPD_DATA_PATH=/data/current.enc.json
WORKDIR /app
COPY requirements.txt .
RUN python -m pip install --no-cache-dir --upgrade pip==26.2 setuptools==84.1.0 && pip install --no-cache-dir -r requirements.txt && useradd --create-home --uid 10001 rpd && mkdir /data && chown rpd:rpd /data
COPY backend ./backend
COPY web ./web
USER rpd
EXPOSE 8765
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8765", "--workers", "1", "--no-access-log", "--proxy-headers"]
