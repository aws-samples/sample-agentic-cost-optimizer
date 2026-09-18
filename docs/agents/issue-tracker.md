# Issue tracker: GitHub

Issues and PRDs for this repo live as GitHub issues. Use the `gh` CLI for all operations.

## Conventions

- **Create an issue**: `gh issue create --title "..." --body "..."`. Use a heredoc for multi-line bodies.
  - Titles follow the repo's issue-template prefixes: `Bug: ...`, `Feature request: ...`, or `Maintenance: ...` (`gh` bypasses the web templates, so apply the convention manually).
  - Apply a triage-state label at creation: `needs-triage` normally; issues that are already fully specified (e.g. `/to-issues` output) may go straight to `ready-for-agent`.
  - Type labels (`bug`, `enhancement`, `documentation`) are a separate axis from triage-state labels — an issue keeps its type label throughout and has exactly one state label at a time.
- **Read an issue**: `gh issue view <number> --comments`, filtering comments by `jq` and also fetching labels.
- **List issues**: `gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'` with appropriate `--label` and `--state` filters.
- **Comment on an issue**: `gh issue comment <number> --body "..."`
- **Apply / remove labels**: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **Close**: `gh issue close <number> --comment "..."`

Infer the repo from `git remote -v` — `gh` does this automatically when run inside a clone.

## When a skill says "publish to the issue tracker"

Create a GitHub issue.

## When a skill says "fetch the relevant ticket"

Run `gh issue view <number> --comments`.
