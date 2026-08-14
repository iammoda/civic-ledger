# Backend image: FastAPI API + arq worker (pick the process via the command).
#
#   docker build -t civic-ledger-backend -f backend/Dockerfile .
#   docker run civic-ledger-backend                             # API on :8000
#   docker run civic-ledger-backend python -m arq app.workers.main.WorkerSettings
#
# Playwright/patchright (script-only deps for the lobby-export refresher) are
# excluded — see requirements notes. Migrations run via:
#   docker run civic-ledger-backend alembic upgrade head
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
# Browser-automation deps are only used by scripts/refresh_lobby_export.py on
# an operator machine; keep the service image lean.
RUN grep -vE '^(playwright|patchright)' requirements.txt > requirements-server.txt \
    && pip install --no-cache-dir -r requirements-server.txt

COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./alembic.ini

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
