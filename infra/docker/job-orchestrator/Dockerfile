FROM python:3.12-slim

WORKDIR /opt/exobrain/job-orchestrator

COPY apps/job-orchestrator/pyproject.toml ./pyproject.toml
COPY apps/job-orchestrator/app ./app

RUN pip install --no-cache-dir .

CMD ["python", "-m", "app.main_worker"]
