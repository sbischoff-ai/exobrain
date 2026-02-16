# Exobrain Assistant Frontend

SvelteKit + Skeleton frontend for the Exobrain chatbot UI.

## Local build and run

From the repository root:

```bash
./scripts/local/build-assistant-frontend.sh
./scripts/local/run-assistant-frontend.sh
```

Notes:
- Re-run `build-assistant-frontend.sh` after changing frontend source.
- Dependency installation is skipped unless `node_modules` is missing or `package-lock.json` changed.
