# Assistant Backend Metastore SQL Assets

This directory is dedicated to the Python assistant backend schema and seed data.

- `migrations/`: TOML Reshape migrations for `assistant_db`
- `seeds/`: development seed records

Apply locally with:

```bash
./scripts/local/assistant-db-setup.sh
```

Validate migrations with:

```bash
reshape check --dirs infra/metastore/assistant-backend/migrations
```
