# Assistant Backend Metastore SQL Assets

This directory is dedicated to the Python assistant backend schema and seed data.

- `migrations/`: TOML Reshape migrations for `assistant_db`
- `seeds/`: ordered development seed records (idempotent SQL):
  - `001_test_users.sql`
  - `002_test_conversations.sql`

## Local (Docker Compose) setup

Apply migrations locally with:

```bash
./scripts/local/assistant-db-migrate.sh
```

Apply optional seed data with:

```bash
./scripts/local/assistant-db-seed.sh
```

Reset data and reseed with the full test dataset:

```bash
./scripts/local/assistant-db-reset-and-seed.sh
```

Run migrations and seed in order with:

```bash
./scripts/local/assistant-db-setup.sh
```

## k3d / Kubernetes setup

For a running local k3d cluster with the Helm chart deployed, run migrations with:

```bash
./scripts/k3d/assistant-db-migrate.sh
```

Apply optional seed data with:

```bash
./scripts/k3d/assistant-db-seed.sh
```

Run both in order with:

```bash
./scripts/k3d/assistant-db-setup.sh
```

The Helm chart models migrations and seed data as separate hook jobs (`dbJobs.assistantBackendMigrations` and `dbJobs.assistantBackendSeed`) so they can be triggered independently.

For native agent workflows, you can fully reset and reseed with:

```bash
./scripts/agent/assistant-db-reset-and-seed-native.sh
```

Recent migration note:
- `004_fix_message_sequence_backfill.toml` backfills `messages.sequence` using per-conversation chronological ranking and removes the legacy `0` default to prevent new rows from inheriting invalid cursor values.

## Migration validation

Validate migrations with:

```bash
reshape check --dirs infra/metastore/assistant-backend/migrations
```


## Related docs

- Assistant backend README: [`../../../apps/assistant-backend/README.md`](../../../apps/assistant-backend/README.md)
- Local setup workflow: [`../../../docs/development/local-setup.md`](../../../docs/development/local-setup.md)
- k3d workflow: [`../../../docs/development/k3d-workflow.md`](../../../docs/development/k3d-workflow.md)
- Engineering standards: [`../../../docs/standards/engineering-standards.md`](../../../docs/standards/engineering-standards.md)
