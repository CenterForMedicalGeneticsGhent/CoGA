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

FROM base AS dev
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

FROM base AS production
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
