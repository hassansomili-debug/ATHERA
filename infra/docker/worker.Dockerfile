FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv

RUN apt-get update && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY apps/api apps/api
COPY services/worker services/worker
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e apps/api -e services/worker

RUN useradd --system --uid 10002 athera && chown -R athera /srv
USER athera

ENV PYTHONPATH=/srv/apps/api:/srv/services/worker
CMD ["python", "-m", "athera_worker.main"]
