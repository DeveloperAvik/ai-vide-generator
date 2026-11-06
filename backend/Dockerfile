FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core espeak-ng curl && rm -rf /var/lib/apt/lists/* \
 && useradd -m -u 10001 studio
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt piper-tts
COPY backend/ /app/
COPY ai/ /ai/
COPY avatar/ /avatar/
ENV AI_DIR=/ai STORAGE_ROOT=/data/local
USER studio
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD curl -fs http://localhost:8000/api/health || exit 1
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
