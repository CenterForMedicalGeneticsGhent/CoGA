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

EXPOSE 8000

FROM base AS dev
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

FROM base AS production
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
