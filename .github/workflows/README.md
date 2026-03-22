# Workflow Notes

This directory contains CI/CD workflows. This note explains why workflows are
written as they are, with security and auditability as defaults.

## Least-Privilege Model

- Workflows default to `permissions: read-all`.
- Jobs request extra scopes only when required.
- Examples:
  - `dependency-action.yml` requests `pull-requests: write` to post review
    summaries.
  - `lint.yml` uses `statuses: write` to publish commit status contexts.
  - Most jobs keep `contents: read` only.

## GitHub App Usage

Two workflows mint GitHub App tokens instead of using broad `GITHUB_TOKEN`
writes:

- `scorecard.yml`
- `dependabot-snapshots.yml` (update OpenAPI snapshots)

This keeps write operations explicit and reduces default token blast radius.

## Dependency Review (`dependency-action.yml`)

Normal PR behavior:

- On `pull_request`, dependency-review compares only PR-introduced dependency
  changes.

Manual full-graph check behavior:

- On `workflow_dispatch`, `base-ref` is set to the repository root commit and
  `head-ref` is set to `github.sha`.
- This forces a one-off review of the full dependency graph in the branch.
- `|| ''` is intentional so non-dispatch events pass empty strings instead of
  boolean `false`.

License policy behavior:

- Policy lists live in `.github/dependency-review-config.yml`.
- `allow-licenses` is the explicit accepted SPDX allow-list.
- `allow-dependencies-licenses` is a version-pinned exception list for
  dependencies where license detection is currently unknown, with inline license
  notes for auditability.
- Keep exceptions narrow (package + version) and remove entries when upstream
  metadata becomes detectable.

## Linter Configuration

- `lint.yml` runs Super-Linter with shared configs from `.github/linters`.
- Local `prek` hooks use the same config files where possible.
- PR summary comments are disabled; run summaries are kept in the Actions step
  summary.

## ClusterFuzzLite

- `cflite_pr.yml` runs `code-change` mode for fast PR feedback.
- `cflite_coverage.yml` and `cflite_weekly.yml` provide broader coverage and
  longer fuzz windows.

### How the Three Modes Work Together

- `cflite_pr.yml` is the fast gate on pull requests. It runs `mode: code-change`
  for a short window (`fuzz-seconds: 300`) and focuses effort around code
  touched by the PR.
- `cflite_coverage.yml` is the scheduled coverage baseline run. It runs with
  `sanitizer: coverage` and `mode: coverage` to refresh corpus and coverage
  artifacts used as guidance for future fuzzing.
- `cflite_weekly.yml` is the deeper bug-hunting run. It runs `mode: batch` with
  a longer time budget (`fuzz-seconds: 3600`) across all configured targets to
  find issues outside the immediate PR surface.

Practical mental model:

- PR = quick, targeted safety net for changed code.
- Coverage = baseline and visibility into explored code paths.
- Weekly = slower, broader sweep for latent defects.

### ClusterFuzzLite `gh-pages` Storage

ClusterFuzzLite uses `gh-pages` as a Git-backed storage branch.

- Configured workflows:
  - `cflite_pr.yml`
  - `cflite_coverage.yml`
  - `cflite_weekly.yml`
- Workflows that can write:
  - `cflite_coverage.yml` (`contents: write`)
  - `cflite_weekly.yml` (`contents: write`)
- PR fuzzing (`cflite_pr.yml`) points at the same storage branch for corpus
  reuse, but does not request `contents: write`.

What is stored there:

- Fuzzer corpus state used to seed future runs.
- Coverage report artifacts produced by coverage mode.
- ClusterFuzzLite run metadata used to improve subsequent runs.
