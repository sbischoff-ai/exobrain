# docs-update

## Use this skill when

- Task is documentation-first (`README`, `docs/`, workflow guides, agent instructions).
- Task introduces/changes scripts and requires command docs to stay accurate.
- Task requires cross-linking to canonical runbooks instead of duplicating procedural details.

## Canonical references

- [`AGENTS.md`](../../AGENTS.md)
- [`docs/README.md`](../../docs/README.md)
- [`docs/agents/codex-runbook.agent.md`](../../docs/agents/codex-runbook.agent.md)
- [`docs/standards/documentation-standards.md`](../../docs/standards/documentation-standards.md)

## Command sequence (exact repo commands for doc verification)

1. Validate referenced agent scripts exist:

```sh
ls scripts/agent
```

2. Validate docs reference expected runbook and setup files:

```sh
rg -n "codex-runbook.agent.md|native-infra-up.sh|run-assistant-frontend-mock.sh|run-assistant-backend-offline.sh" docs AGENTS.md skills
```

3. Check markdown and repository diff hygiene:

```sh
git diff --check
```

## Failure handling

- **Referenced script/doc path missing**
  - Update links/commands to existing files and re-run the checks.
- **Environment tool missing for optional checks**
  - Fall back to shell-native checks (`rg`, `git diff --check`) and report limitation.
- **Conflicting or duplicated instructions**
  - Keep `AGENTS.md` and `docs/agents/codex-runbook.agent.md` as canonical sources; trim duplicate procedural blocks from other docs and link to canon.

## Expected verification output

- `rg` returns expected references for scripts/docs.
- `git diff --check` returns no whitespace/conflict warnings.
- New/updated docs use working relative links.

## Rollback / cleanup

- Revert incorrect documentation edits with:

```sh
git checkout -- <path>
```

- Re-run verification commands after edits are corrected.
