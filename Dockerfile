FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        gcc \
        libxml2-dev \
        libxslt1-dev \
        libffi-dev \
        libssl-dev \
        libpq-dev \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir poetry

COPY pyproject.toml poetry.lock* ./

RUN poetry install --no-ansi --only main --no-root

COPY ./talk2dom ./talk2dom
COPY alembic.ini ./
COPY ./alembic ./alembic

EXPOSE 8000

# Fresh DB (no alembic_version yet): stamp head, the app's create_all builds the schema.
# Existing DB: apply pending migrations.
CMD ["sh", "-c", "if [ -n \"$(alembic current)\" ]; then alembic upgrade head; else alembic stamp head; fi && exec uvicorn talk2dom.api.main:app --host 0.0.0.0 --port 8000"]