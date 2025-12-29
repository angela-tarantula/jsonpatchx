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

## FastAPI OpenAPI demo (local)

This repo includes a small FastAPI app at `examples/fastapi_openapi.py`. It exposes OpenAPI
documentation automatically.

### Run it

1. Install the FastAPI extras for this repo:

```sh
uv sync --group fastapi
```

2. Start the server:

```sh
uv run uvicorn examples.fastapi_openapi:app --reload
```

3. Open it in your browser:

- Swagger UI: http://127.0.0.1:8000/docs
- OpenAPI JSON: http://127.0.0.1:8000/openapi.json
- ReDoc: http://127.0.0.1:8000/redoc

### Stop it

Press `Ctrl+C` in the terminal window where the server is running. That cleanly shuts it down.
If you accidentally ran the command twice and got two terminals running, stop both.

### Handy extras to try

- Health check: http://127.0.0.1:8000/health
- Fetch a user: http://127.0.0.1:8000/users/1
- Try a patch in Swagger UI (`/users/{user_id}` or `/configs/{config_id}`), then reload the GET endpoint.
