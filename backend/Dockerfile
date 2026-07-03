FROM python:3.10-slim AS base

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

# `--proxy-headers` makes uvicorn honour X-Forwarded-For/Proto from a trusted
# front end so `request.client.host` is the real client IP (needed for the signup
# rate-limit bucket and audit logging — behind Cloud Run / a GCP HTTPS LB the raw
# peer is a Google-internal IP). uvicorn only trusts forwarded headers from peers
# in FORWARDED_ALLOW_IPS (default 127.0.0.1); set that env to the trusted proxy
# range in the runtime (see terraform/cloudrun.tf FORWARDED_ALLOW_IPS).
FROM base AS dev
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--reload"]

FROM base AS production
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
