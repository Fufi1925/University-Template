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

# Ablageort der Premium-Freischaltungen.
#
# Bewusst OHNE die Docker-Anweisung VOLUME: Railway lehnt Dockerfiles mit
# VOLUME ab ("docker VOLUME ... is not supported, use Railway Volumes") und
# verwaltet persistenten Speicher ausschliesslich ueber das Dashboard.
#
# Railway:  Settings -> Volumes -> Mount path = /app/data
# Docker:   docker run -v architect-data:/app/data ...
#
# Ohne gemountetes Volume laeuft der Bot normal weiter, die Freischaltungen
# sind dann aber nach jedem Redeploy weg.
RUN mkdir -p /app/data

CMD ["python", "bot.py"]
