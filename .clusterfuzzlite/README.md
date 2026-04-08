# ClusterFuzzLite Runbook

This is the canonical documentation for
[ClusterFuzzLite](https://google.github.io/clusterfuzzlite/) in this repository.

For local fuzzing setup and commands, see
[`fuzzers/README.md`](../fuzzers/README.md).

## What Lives Here

- [`Dockerfile`](Dockerfile): build image and Python runtime for
  OSS-Fuzz/ClusterFuzzLite.
- [`build.sh`](build.sh): compiles fuzzer targets and packages seed
  corpora/dictionaries.
- [`project.yml`](project.yml): ClusterFuzzLite project metadata
  (`language: python`).
- [`requirements-bootstrap.txt`](requirements-bootstrap.txt): pinned bootstrap
  dependencies used by the Docker build.

## Fuzz Targets Built

From [`build.sh`](build.sh):

- [`jsonpatchx_fuzzer.py`](../fuzzers/jsonpatchx_fuzzer.py)
- [`jsonpatchx_custom_backend_fuzzer.py`](../fuzzers/jsonpatchx_custom_backend_fuzzer.py)

Associated dictionaries and seed corpus ZIP files are copied into `$OUT`.

## Workflow Overview

- PR (`code-change`) is the fast, targeted safety net.
- Coverage (`coverage`) maintains baseline data and visibility into explored
  paths.
- Weekly (`batch`) spends more time across targets to find latent issues not
  near current PR changes.

## Workflow Details and Responsibilities

These workflows consume the `.clusterfuzzlite` build/config:

1. [`cflite_pr.yml`](../.github/workflows/cflite_pr.yml)
   - Trigger: `pull_request` to `main` and `workflow_dispatch`.
   - Mode: `code-change`
   - Sanitizer: `address`
   - Time budget: `fuzz-seconds: 300`
   - `keep-unaffected-fuzz-targets: false`
   - PRs only fuzz when fuzz-relevant inputs changed: `jsonpatchx/`, `fuzzers/`,
     `.clusterfuzzlite/`, `pyproject.toml`, `uv.lock`, or one of the
     ClusterFuzzLite workflow YAMLs. The required `fuzz-code-changes` job still
     runs on every PR and exits green when none of those paths changed.
   - Purpose: fast PR signal focused on changed code areas.

2. [`cflite_coverage.yml`](../.github/workflows/cflite_coverage.yml)
   - Trigger: weekly schedule `0 2 * * 0` (Sunday 02:00 UTC) and
     `workflow_dispatch`.
   - Mode: `coverage`
   - Sanitizer: `coverage`
   - `keep-unaffected-fuzz-targets: true`
   - Purpose: refresh coverage baseline/corpus guidance.

3. [`cflite_weekly.yml`](../.github/workflows/cflite_weekly.yml)
   - Trigger: weekly schedule `30 2 * * 0` (Sunday 02:30 UTC) and
     `workflow_dispatch`.
   - Mode: `batch`
   - Sanitizer: `address`
   - Time budget: `fuzz-seconds: 3600`
   - `keep-unaffected-fuzz-targets: true`
   - Purpose: deeper whole-target bug discovery.

## `fuzz-corpus` Storage Model

All three workflows are configured to use `fuzz-corpus` as the storage branch:

- `storage-repo-branch: fuzz-corpus`
- `storage-repo-branch-coverage: fuzz-corpus`

Write permissions:

- [`cflite_coverage.yml`](../.github/workflows/cflite_coverage.yml): has
  `contents: write` and can push coverage/corpus updates.
- [`cflite_weekly.yml`](../.github/workflows/cflite_weekly.yml): has
  `contents: write` and can push corpus updates.
- [`cflite_pr.yml`](../.github/workflows/cflite_pr.yml): does not request
  `contents: write`; it reuses stored data for guidance but is not expected to
  publish updates.

Stored artifacts include seed/corpus state, coverage reports, and run metadata
used by subsequent runs.
