FROM python:3.11-slim
WORKDIR /app
COPY apps/assistant-backend/pyproject.toml ./
COPY apps/assistant-backend/app ./app
RUN pip install --no-cache-dir .
ENV LOG_LEVEL=INFO
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
