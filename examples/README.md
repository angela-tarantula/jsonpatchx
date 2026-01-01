# Examples: jsonpatch demo suite

A focused set of demos showing how to use jsonpatch for typed, registry-driven patching.
Baselines are an afterthought: use them only if you want to sanity-check the contrast.

## Quick start (30-second tour)

Run the CLI demo to see the core patch engine without any server:

```bash
uv run python -m examples.standard.cli_apply
```

## Table of contents

- [Demo 1: The standard model patch](#demo-1-the-standard-model-patch)
- [Demo 2: Untyped document patching](#demo-2-untyped-document-patching)
- [Demo 3: First-class custom operations](#demo-3-first-class-custom-operations)
- [Demo 4: Custom ops + Pydantic models](#demo-4-custom-ops--pydantic-models)
- [Demo 5: Custom pointer backends](#demo-5-custom-pointer-backends)
- [Baselines (optional)](#baselines-optional)
- [Extras](#extras)

## Setup (once)

- Install demo deps: `uv sync --group fastapi`
- Run commands from the repo root.

## How to read the demos

- Swagger: `http://127.0.0.1:PORT/docs`
- OpenAPI JSON: `http://127.0.0.1:PORT/openapi.json`
- ReDoc: `http://127.0.0.1:PORT/redoc`

## Demo launcher (quality-of-life)

Use the launcher to start a demo without juggling ports:

```bash
uv run python -m examples.demo
```

## Demo 1: The standard model patch

**Goal:** patch a Pydantic model with full type safety.

**File:** `examples.standard.api_typed_model`

**Feature:** `JsonPatchFor[User]` generates a discriminated union in OpenAPI.

**Run**

- `uvicorn examples.standard.api_typed_model:app --reload --port 8000`

**Links**

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/openapi.json`

## Demo 2: Untyped document patching

**Goal:** apply typed operations to raw JSON/Dict documents.

**File:** `examples.standard.api_untyped_doc`

**Feature:** `make_json_patch_body` for flexible JSON schemas.

**Run**

- `uvicorn examples.standard.api_untyped_doc:app --reload --port 8001`

**Links**

- `http://127.0.0.1:8001/docs`
- `http://127.0.0.1:8001/openapi.json`

## Demo 3: First-class custom operations

**Goal:** add domain-specific ops like increment or toggle.

**File:** `examples.custom_ops.api_custom_ops_typed`

**Feature:** custom ops appear in OpenAPI with their own schemas.

**Run**

- `uvicorn examples.custom_ops.api_custom_ops_typed:app --reload --port 8002`

**Links**

- `http://127.0.0.1:8002/docs`
- `http://127.0.0.1:8002/openapi.json`

## Demo 4: Custom ops + Pydantic models

**Goal:** bind custom registries to specific Pydantic models.

**File:** `examples.custom_ops.api_custom_ops_model`

**Feature:** registry-driven dispatch with model-aware validation.

**Run**

- `uvicorn examples.custom_ops.api_custom_ops_model:app --reload --port 8003`

**Links**

- `http://127.0.0.1:8003/docs`
- `http://127.0.0.1:8003/openapi.json`

## Demo 5: Custom pointer backends

**Goal:** change how paths are parsed (e.g., using dot.notation).

**File:** `examples.pointer_backends.api_custom_pointer`

**Feature:** registry-scoped backends swap pointer logic without changing ops.

**Run**

- `uvicorn examples.pointer_backends.api_custom_pointer:app --reload --port 8004`

**Links**

- `http://127.0.0.1:8004/docs`
- `http://127.0.0.1:8004/openapi.json`

---

## Baselines (optional)

These are only here for contrast. They are intentionally incomplete.

- Loose schema: `uvicorn examples.baselines.average.api_loose_schema:app --reload --port 8010`
- Ad-hoc custom ops: `uvicorn examples.baselines.average.api_ad_hoc_custom:app --reload --port 8011`
- Best-effort union ops: `uvicorn examples.baselines.best_effort.api_union_ops:app --reload --port 8012`
- Best-effort custom union: `uvicorn examples.baselines.best_effort.api_custom_union_ops:app --reload --port 8013`

## Extras

- Error semantics: `python -m examples.standard.failures`
- Custom ops CLI: `python -m examples.custom.cli_apply`
- REST snippets: `examples/_shared/clients.http`
