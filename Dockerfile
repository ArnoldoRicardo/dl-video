FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data && \
    addgroup --system app && \
    adduser --system --ingroup app app && \
    chown -R app:app /app

USER app

HEALTHCHECK --interval=60s --timeout=10s --retries=3 \
    CMD python -c "import asyncio; from src.config import settings; print('ok')" || exit 1

CMD ["python", "main.py"]
