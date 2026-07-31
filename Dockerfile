FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

# Installiert wird aus dem Lockfile, nicht aus requirements.txt: dort stehen
# nur Bereiche (">=2.6,<3.0"), sodass ein Patch-Release das Image veraendern
# koennte, ohne dass ein Commit stattgefunden hat. --require-hashes lehnt
# ausserdem jedes Paket ab, dessen Inhalt nicht zum Lockfile passt.
COPY requirements.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements.lock

COPY config.py web.py bot.py ./
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
#
# Der Bot braucht keinerlei Root-Rechte. Laeuft der Prozess trotzdem als root,
# hat ein Fehler in einer Abhaengigkeit vollen Zugriff auf den Container —
# deshalb ein eigener Benutzer, dem nur /app/data gehoert.
RUN useradd --create-home --uid 10001 app \
 && mkdir -p /app/data \
 && chown -R app:app /app
USER app

# Prueft denselben Endpunkt wie Railway, aber von innen: damit faellt ein
# haengender Bot auch bei "docker run" ohne Plattform auf.
HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT','8080') + '/health', timeout=4)"

CMD ["python", "bot.py"]
