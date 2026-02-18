# Major Changes Log

Purpose: keep a concise record of major incidents/fixes that may help future debugging.

Guidelines:
- Add entries only when they materially improve future diagnosis.
- Keep entries short: date, scope, symptom, root cause, fix, verification.
- Do not duplicate routine feature/change summaries already clear from Git history.

## Entries

### 2026-02-18 — assistant-frontend dev SSR/runtime mismatch
- **Scope:** `apps/assistant-frontend`
- **Symptom:** frontend dev server returned HTTP 500 on `/`.
- **Root cause:** Svelte/Kit/Vite toolchain misalignment plus SSR-incompatible global Vite `resolve.conditions` override.
- **Fix:** aligned frontend dependency set and scoped `resolve.conditions = ['browser']` to Vitest only.
- **Verification:** `npm run dev` returned 200; `npm run build` and `npm test` passed.
