## Development

### Commands

```bash
make setup    # one-time: install Python (uv) + Node deps, pre-commit hooks
make check    # run all code quality checks (pre-commit: ruff, prettier)
make test     # run all tests (pytest + vitest)
make synth    # synthesize CDK stack — runs cdk-nag checks
```

Targeted commands (`uv run pytest tests/test_journal.py`, `npx vitest run` in `infra/`) are fine while iterating. Before committing or opening a PR, verification is `make check && make test` — nothing else counts as green. Changes under `infra/` additionally require `make synth` (cdk-nag only runs during synth, not in the vitest suite; CI has a dedicated job for it).

Evals (`make eval AGENT=<name>`) cost real Bedrock tokens. Never run them automatically — only when explicitly asked.

### Pull requests

- PR titles MUST use conventional-commit format (enforced by `.github/semantic.yml`; the repo squash-merges, so the title is what lands on main).
- PR descriptions MUST follow `.github/PULL_REQUEST_TEMPLATE.md` (issue number, Summary with Changes and User experience). Use `N/A` for the issue number only where the issue-first policy below doesn't require one.
- Commit messages SHOULD use conventional-commit format too.
- Feature and non-trivial bug work starts as a GitHub issue and reaches `ready-for-agent` before implementation. Chores, docs, and trivial fixes may go straight to PR with a clear description.

Contribution policy and local development setup: see `CONTRIBUTING.md` and the README.

## Agent skills

### Issue tracker

Issues live in this repo's GitHub Issues, via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default label vocabulary (needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.
