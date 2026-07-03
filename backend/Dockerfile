# Pin the base image by digest (tag kept for readability) so builds are reproducible
# — an IVDR requirement — and don't drift if the upstream tag is repushed.
FROM python:3.10-slim@sha256:5f9928ea39771e8ddf4fb9a96ab24f65f087793635614405a1dc9384f040852e AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/db ./db
COPY backend/app ./app
# Ship the clinical CNV knowledgebase build script so the admin "rebuild
# knowledgebase" action can invoke it (see CLINICAL_CNV_KB_SCRIPT_PATH).
COPY scripts ./scripts

# Build identity, injected via --build-arg (see docker-compose build args). Placed
# after the dependency layers so changing the SHA doesn't bust the pip-install cache.
# Baked into the base image as ENV so both dev and production runtimes report it via
# Settings (the .git dir is excluded from the build context, so the short SHA must be
# passed in by the build invoker, e.g. GIT_SHA="$(git rev-parse --short=12 HEAD)").
ARG APP_VERSION=0.0.0+unknown
ARG GIT_SHA=unknown
ENV APP_VERSION=${APP_VERSION} \
    GIT_SHA=${GIT_SHA}

EXPOSE 8000

FROM base AS dev
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

FROM base AS production
# Drop root: create an unprivileged user and give it the app tree + the /data mount
# point. In Cloud Run /data/ref-data is a read-only gcsfuse mount (world-readable, so
# a non-root UID can read it) and PHI family data goes to GCS via the API — not this
# path. Local docker-compose bind-mounts a host-owned ./data and overrides
# `user: root` to keep that writable; the hardening targets the deployed image default.
RUN groupadd --system --gid 10001 appuser \
    && useradd --system --uid 10001 --gid appuser --home-dir /app --shell /usr/sbin/nologin appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /app /data
USER appuser
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
