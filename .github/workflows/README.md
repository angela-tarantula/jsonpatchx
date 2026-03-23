# Workflow Notes

This directory contains CI/CD workflows. This note explains why workflows are
written as they are, with security and auditability as defaults.

## Least-Privilege Model

- Workflows default to `permissions: read-all`.
- Jobs request extra scopes only when required.
- Examples:
  - [`dependency-action.yml`](dependency-action.yml) requests
    `pull-requests: write` to post review summaries.
  - [`lint.yml`](lint.yml) uses `statuses: write` to publish commit status
    contexts.
  - Most jobs keep `contents: read` only.

## GitHub App Usage

Two workflows mint GitHub App tokens instead of using broad `GITHUB_TOKEN`
writes:

- [`scorecard.yml`](scorecard.yml)
- [`dependabot-snapshots.yml`](dependabot-snapshots.yml) (update OpenAPI
  snapshots)

This keeps write operations explicit and reduces default token blast radius.

## Codecov Coverage Model

- Coverage uploads run once per supported runtime in the Python matrix (`3.12`,
  `3.13`, `3.14`), with runtime flags:
  - `py-3.12`
  - `py-3.13`
  - `py-3.14`
- This is intentional: repository coverage represents "covered in any supported
  runtime", while still allowing per-runtime inspection via flags.
- Codecov behavior is configured in [`codecov.yml`](../codecov.yml).

## Dependency Review ([`dependency-action.yml`](dependency-action.yml))

Normal PR behavior:

- On `pull_request`, dependency-review compares only PR-introduced dependency
  changes.

Manual full-graph check behavior:

- On `workflow_dispatch`, `base-ref` is set to the repository root commit and
  `head-ref` is set to `github.sha`.
- This forces a one-off review of the full dependency graph in the branch.

License policy behavior:

- Policy lists live in
  [`dependency-review-config.yml`](../dependency-review-config.yml).
- `allow-licenses` is the explicit accepted SPDX allow-list.
- `allow-dependencies-licenses` is a version-pinned exception list for
  dependencies where license detection is currently unknown, with inline license
  notes for auditability.
- Keep exceptions narrow (package + version) and remove entries when upstream
  metadata becomes detectable.

## Linter Configuration

- [`lint.yml`](lint.yml) runs Super-Linter with shared configs from
  [`linters`](../linters/README.md).
- Local `prek` hooks use the same config files where possible.
- PR summary comments are disabled; run summaries are kept in the Actions step
  summary.

## ClusterFuzzLite

Canonical [runbook](../../.clusterfuzzlite/README.md).

Quick trigger/permission summary:

- [`cflite_pr.yml`](cflite_pr.yml)
  - Triggers: `pull_request` and `workflow_dispatch`
  - Write scopes: `security-events: write` only
- [`cflite_coverage.yml`](cflite_coverage.yml)
  - Triggers: weekly schedule and `workflow_dispatch`
  - Write scopes: `contents: write`, `security-events: write`
- [`cflite_weekly.yml`](cflite_weekly.yml)
  - Triggers: weekly schedule and `workflow_dispatch`
  - Write scopes: `contents: write`, `security-events: write`
