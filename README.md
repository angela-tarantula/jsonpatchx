# json-patch
[![CI](https://github.com/angela-tarantula/jsonpatch/actions/workflows/python-app.yml/badge.svg?branch=main)](https://github.com/marketplace/actions/super-linter)

## About The Project

This is an RFC 6902 (JSON Patch) / RFC 7396 (JSON Merge Patch) implementation for Python.

## Getting Started

To get a local copy up and running follow these simple steps.

### Prerequisites

[Install uv](https://docs.astral.sh/uv/getting-started/installation/#installing-uv)

```sh
python -m pip install --upgrade pip uv
```

### Installation

1. Clone the repository

```sh
git clone https://github.com/angela-tarantula/json-patch
```

2. Install the dependencies

```sh
uv sync
```

## FastAPI OpenAPI demos (local)

These examples are designed for first-time FastAPI users. They let you compare the OpenAPI output
from this library against a more typical, looser PATCH schema.

### Run the OpenAPI comparison (standard RFC 6902 ops)

1. Install the FastAPI extras for this repo:

```sh
uv sync --group fastapi
```

2. Start the library-powered demo (port 8000):

```sh
uv run uvicorn examples.openapi_demo:app --reload --port 8000
```

3. Start the baseline demo (port 8001):

```sh
uv run uvicorn examples.openapi_baseline:app --reload --port 8001
```

4. Open the docs side-by-side:

- Library demo Swagger: http://127.0.0.1:8000/docs
- Library demo OpenAPI JSON: http://127.0.0.1:8000/openapi.json
- Library demo ReDoc: http://127.0.0.1:8000/redoc
- Baseline demo Swagger: http://127.0.0.1:8001/docs
- Baseline demo OpenAPI JSON: http://127.0.0.1:8001/openapi.json
- Baseline demo ReDoc: http://127.0.0.1:8001/redoc

### Run the custom-ops comparison

This shows how custom operations appear in OpenAPI when registered with this library vs a
hand-rolled baseline.

Start the library demo (port 8002):

```sh
uv run uvicorn examples.custom_ops_demo:app --reload --port 8002
```

Start the baseline demo (port 8003):

```sh
uv run uvicorn examples.custom_ops_baseline:app --reload --port 8003
```

Open the docs:

- Custom ops demo Swagger: http://127.0.0.1:8002/docs
- Custom ops demo OpenAPI JSON: http://127.0.0.1:8002/openapi.json
- Custom ops demo ReDoc: http://127.0.0.1:8002/redoc
- Custom ops baseline Swagger: http://127.0.0.1:8003/docs
- Custom ops baseline OpenAPI JSON: http://127.0.0.1:8003/openapi.json
- Custom ops demo ReDoc: http://127.0.0.1:8003/redoc

### Stop the servers

Press `Ctrl+C` in each terminal window where a server is running. That cleanly shuts it down.

### Handy extras to try

- Health check (demo): http://127.0.0.1:8000/health
- Health check (baseline): http://127.0.0.1:8001/health
- Fetch a user (demo): http://127.0.0.1:8000/users/1
- Try patch examples in Swagger UI, then re-run the GET endpoints to see changes


## Design notes: typed, explicit patch semantics

This library intentionally treats typing as a runtime contract, not just static metadata.

### JSONPointer[T] is enforced at runtime
- `get(doc)` validates that the resolved value is a `T`.
- `add(doc, value)` (by default) validates that `value` is a `T` before writing.
- `remove(doc)` is intentionally **type-gated**: it resolves and validates the target as `T` before removing.

This makes patch behavior explicit and prevents accidental schema drift:
- `JSONPointer[JSONValue]` is permissive (“operate on any JSON value”).
- `JSONPointer[JSONBoolean]` is restrictive (“operate only when the current value is a boolean”).

If you want permissive behavior, widen `T` (e.g. `JSONValue` or `JSONNumber | JSONString`) or define a permissive operation in your registry.

### Covariance is intentional
`JSONPointer` is covariant in `T`. This allows composing operations while preserving stricter guarantees.
For example, a custom op that carries `JSONPointer[JSONBoolean]` can reuse that pointer when delegating to `AddOp`,
preserving boolean-specific enforcement.
