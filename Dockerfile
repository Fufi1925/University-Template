FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY config.py health.py bot.py ./
COPY core/ ./core/
COPY ui/ ./ui/
COPY templates/ ./templates/

# Persist premium unlocks across restarts when a volume is mounted here.
RUN mkdir -p /app/data
VOLUME ["/app/data"]

CMD ["python", "bot.py"]
