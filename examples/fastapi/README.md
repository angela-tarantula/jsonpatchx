# Examples: jsonpatchx demo suite

Four focused FastAPI demos. Each demo is a standalone file that reads cleanly in Swagger UI.

## Setup (once)

- Install demo deps: `uv sync --group fastapi`
- Run commands from the repo root.

## Quick links

- Swagger: `http://127.0.0.1:PORT/docs`
- OpenAPI JSON: `http://127.0.0.1:PORT/openapi.json`
- ReDoc: `http://127.0.0.1:PORT/redoc`

## Demo launcher

```bash
uv run python -m examples.fastapi.demo
```

FastAPI docs already include example requests and payloads.

## Demo 1: Support desk corrections

Standard JSON Patch on customer profiles using `JsonPatchFor[Model, StandardRegistry]`.

**File:** `examples/fastapi/demo1.py`

**Run**

- `uv run uvicorn examples.fastapi.demo1:app --reload --port 8000`

## Demo 2: Player and guild progression

Custom registries per model (players vs guilds) using `JsonPatchFor[Model, CustomRegistry]`.

**File:** `examples/fastapi/demo2.py`

**Run**

- `uv run uvicorn examples.fastapi.demo2:app --reload --port 8001`

## Demo 3: Control plane configs

Plain JSON patching for service configs using `JsonPatchFor[Name, Registry]`.

**File:** `examples/fastapi/demo3.py`

**Run**

- `uv run uvicorn examples.fastapi.demo3:app --reload --port 8002`

## Demo 4: Spellbook rune pointers

Registry-scoped rune-pointer backends for spellbook and apprentice settings.
Uses `JsonPatchRoute.dependency()` to inject the validation context.

**File:** `examples/fastapi/demo4.py`

**Run**

- `uv run uvicorn examples.fastapi.demo4:app --reload --port 8003`

This demo uses `JsonPatchRoute.dependency()` to inject Pydantic validation context, which
FastAPI does not currently provide for request bodies.
