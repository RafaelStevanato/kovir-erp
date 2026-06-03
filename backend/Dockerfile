#
# Docker status:
# - Docker remains allowed as a future option for local/dev infrastructure.
# - The previous Kovir ERP Docker/deploy setup was discarded with the AWS/deploy
#   cleanup and must not be treated as an active or validated baseline.
# - If a new Docker setup is needed, design and validate it from scratch.
# - Do not reuse this file as production guidance without a fresh security,
#   dependency, migration, secrets, healthcheck and operational review.
#

FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

RUN groupadd --system kovir \
    && useradd --system --gid kovir --home-dir /app --shell /usr/sbin/nologin kovir

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

RUN chown -R kovir:kovir /app

USER kovir

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read()" || exit 1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --log-level ${UVICORN_LOG_LEVEL:-info}"]
