FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data && \
    addgroup --gid 1000 app && \
    adduser --uid 1000 --gid 1000 --disabled-password --gecos "" app && \
    chown -R app:app /app

USER app

HEALTHCHECK --interval=60s --timeout=10s --retries=3 \
    CMD python -c "import asyncio; from src.config import settings; print('ok')" || exit 1

CMD ["python", "main.py"]
