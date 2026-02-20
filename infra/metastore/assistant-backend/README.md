# Assistant Backend Metastore SQL Assets

This directory is dedicated to the Python assistant backend schema and seed data.

- `migrations/`: TOML Reshape migrations for `assistant_db`
- `seeds/`: development seed records (idempotent SQL)

## Local (Docker Compose) setup

Apply migrations locally with:

```bash
./scripts/local/assistant-db-migrate.sh
```

Apply optional seed data with:

```bash
./scripts/local/assistant-db-seed.sh
```

Run both in order with:

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
