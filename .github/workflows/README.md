# Workflow Notes

This directory contains CI/CD workflows. This note explains why workflows are
written as they are, with security and auditability as defaults.

## OpenAPI Snapshots

- OpenAPI snapshot JSON files are committed artifacts in this repository under
  [`examples/openapi`](../../examples/openapi).
- They make API contract changes visible in PR diffs.
- Therefore it's necessary to regenerate snapshots whenever code or dependencies
  change generated OpenAPI.
- Implementation script:
  [`scripts/update_openapi_snapshots.py`](../../scripts/update_openapi_snapshots.py).
- Local refresh: invoke `prek` hooks or direct script execution.
- CI model:
  [`dependabot-update-openapi-snapshots.yml`](dependabot-update-openapi-snapshots.yml)
  regenerates snapshots on Dependabot dependency updates and commits only when
  snapshot files changed.

## Least-Privilege Model

- Workflows default to `permissions: read-all`.
- Jobs request extra scopes only when required.
- Examples:
  - [`dependency-review.yml`](dependency-review.yml) requests
    `pull-requests: write` to post review summaries.
  - [`lint.yml`](lint.yml) uses `statuses: write` to publish commit status
    contexts.
  - Most jobs keep `contents: read` only.

## GitHub App Usage

Two workflows mint GitHub App tokens instead of using broad `GITHUB_TOKEN`
writes:

- [`scorecard.yml`](scorecard.yml)
- [`dependabot-update-openapi-snapshots.yml`](dependabot-update-openapi-snapshots.yml)

This keeps write operations explicit and reduces default token blast radius.

## Environment-Scoped Secrets

- [`python-tests.yml`](python-tests.yml) uses `environment: codecov-automation`
  on the `build` job.
- `CODECOV_TOKEN` is stored as an environment secret in `codecov-automation`
  instead of a repository secret.
- Environment permissions are not a token-scope model. `GITHUB_TOKEN` scopes are
  still controlled by workflow/job `permissions`.

## Codecov Coverage Model

- Coverage uploads run once per supported runtime in the Python matrix (`3.12`,
  `3.13`, `3.14`), with runtime flags:
  - `py-3.12`
  - `py-3.13`
  - `py-3.14`
- This is intentional: repository coverage represents "covered in any supported
  runtime", while still allowing per-runtime inspection via flags.
- Codecov behavior is configured in [`codecov.yml`](../codecov.yml).

## Dependency Review

PR required-check behavior ([`dependency-review.yml`](dependency-review.yml)):

- On `pull_request`, dependency-review compares only PR-introduced dependency
  changes.
- Snapshot warnings are retried automatically via
  `retry-on-snapshot-warnings: true` with a 10-second timeout to tolerate
  delayed dependency snapshot ingestion.

Manual full-graph audit behavior
([`dependency-review-full-audit.yml`](dependency-review-full-audit.yml)):

- Triggered only by `workflow_dispatch`.
- `base-ref` is computed at runtime as the repository root commit and `head-ref`
  is set to `github.sha`.
- This forces a one-off review of the full dependency graph in the branch.
- The same snapshot-retry settings are enabled here to reduce false warnings
  when dependency snapshots arrive late.

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
