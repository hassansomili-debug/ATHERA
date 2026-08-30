FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv

RUN apt-get update && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY apps/api/pyproject.toml apps/api/pyproject.toml
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -e apps/api

COPY apps/api apps/api
COPY infra/db infra/db

# لا يعمل بجذر | never run as root
RUN useradd --system --uid 10001 athera && chown -R athera /srv
USER athera

EXPOSE 8000
CMD ["uvicorn", "athera_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "apps/api"]
