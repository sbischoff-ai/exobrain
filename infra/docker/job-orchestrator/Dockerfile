FROM python:3.12-slim

RUN apt-get update     && apt-get install -y --no-install-recommends libstdc++6     && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/exobrain/job-orchestrator

COPY apps/job-orchestrator/pyproject.toml ./pyproject.toml
COPY apps/job-orchestrator/app ./app

RUN pip install --no-cache-dir .

CMD ["python", "-m", "app.main_worker"]
