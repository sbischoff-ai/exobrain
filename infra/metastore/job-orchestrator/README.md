# Job Orchestrator Metastore SQL Assets

This directory contains Reshape migrations for the `job_orchestrator_db` database.

- `migrations/`: TOML Reshape migrations for orchestrator job-state tables.

## Local setup

```bash
./scripts/local/job-orchestrator-db-setup.sh
```

Equivalent migrate-only command:

```bash
./scripts/local/job-orchestrator-db-migrate.sh
```

Bootstrap SQL: `infra/docker/metastore/init/02-job-orchestrator-db.sql`.

## Native agent setup

```bash
./scripts/agent/job-orchestrator-db-setup-native.sh
```

## Migration validation

```bash
reshape check --dirs infra/metastore/job-orchestrator/migrations
```
