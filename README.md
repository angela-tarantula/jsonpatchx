# json-patch
[![CI](https://github.com/angela-tarantula/jsonpatch/actions/workflows/python-app.yml/badge.svg?branch=main)](https://github.com/marketplace/actions/super-linter)

## About The Project

A typed, extensible JSON Patch engine for Python.

This library implements RFC 6902 (JSON Patch), but its goal is not just to apply patches.
It is to make patch semantics **explicit, enforceable, and evolvable**.

Most JSON Patch libraries treat paths and values as untyped strings and blobs.
This library treats them as runtime contracts.

## Why this library exists

JSON Patch is deceptively simple. In practice, real applications need more:

- Guarantees that a patch won’t silently corrupt type-safe schema
- Clear, debuggable failure modes
- Domain-specific operations beyond the RFC
- High-quality OpenAPI schemas for PATCH endpoints

## Key Features

- **Extensible Operation Registry**
  Define custom operations (`increment`, `toggle`, `swap`, etc.) that become
  first-class, schema-validated citizens in your API.
- **Typed JSON Pointers**
  `JSONPointer[T]` enforces *what* a path may point to, not just *where* it points.
  Operations fail loudly when the runtime type contract is violated.
- **FastAPI / OpenAPI integration**
  PATCH bodies are generated as fully-typed **discriminated unions**,
  producing precise, professional Swagger documentation automatically.
- **Explicit, atomic failures**
  Validation errors surface structured, debuggable context.
  Patches are all atomic by default and do not mutate state on failure.

## Who this is for

This library is a good fit if you are building:

- APIs that accept PATCH requests and need strong correctness guarantees
- Systems that want typed, explicit JSON Pointer semantics
- FastAPI services that want excellent OpenAPI schemas for PATCH endpoints
- Applications with domain-specific patch operations
- Applications that rely on LLM-generated or LLM-reviewed patch operations

If you want patch semantics to be **explicit, enforceable, and evolvable**, this library is for you.

## Core concepts

**OperationSchema** defines an individual operation as a Pydantic model (standard or custom),
including its fields, validation rules, and `apply()` behavior. Operation schemas are composable
and can delegate to other operations while preserving `JSONPointer[T]` guarantees.

Example:

```py
from typing import Literal, override

from jsonpatch import OperationSchema, ReplaceOp
from jsonpatch.types import JSONBoolean, JSONPointer, JSONValue


class ToggleOp(OperationSchema):
    op: Literal["toggle"] = "toggle"
    path: JSONPointer[JSONBoolean]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        return ReplaceOp(path=self.path, value=not current).apply(doc)
```

**OperationRegistry** is the vocabulary and parsing context. It registers which
OperationSchema types are allowed and builds the discriminated union used for validation. Registries are
explicit, immutable, and composable, so different APIs can safely use different patch semantics side-by-side.

Example:

```py
from jsonpatch import OperationRegistry, AddOp, MoveOp

standard_registry = OperationRegistry.standard()

limited_registry = OperationRegistry(AddOp, MoveOp)

custom_registry = OperationRegistry.with_standard(ToggleOp, ConcatenateOp)
```

**JsonPatch** parses and applies a patch document against a JSON value. It is the core runtime
engine for programmatic patch application.

Example:

```py
from jsonpatch import JsonPatch, ReplaceOp

doc = {"title": "Example", "version": {"name": "draft"}, "ready": False, "here": 4, "there": 2}

ops_1 = [{"op": "replace", "path": "/title", "value": "Updated"}]
ops_2 = [ReplaceOp(path="/version/name", value="v1"), ToggleOp(path="/ready")]
ops_3 = '[{"op": "swap", "a": "/here", "b": "/there"}]'

patch_1 = JsonPatch(ops_1)
patch_2 = JsonPatch(ops_2, registry=custom_registry)
patch_3 = JsonPatch.from_string(ops_3, registry=custom_registry)

doc = patch_1.apply(doc)
doc = patch_2.apply(doc)
doc = patch_3.apply(doc)
```

**JsonPatchFor[Model]** generates a Pydantic RootModel for patching a specific BaseModel and
validates the patched output back into that model.

Example:

```py
from fastapi import Body, FastAPI

from jsonpatch import JsonPatchFor, OperationRegistry

app = FastAPI()

registry = OperationRegistry.with_standard(ToggleOp)
UserPatch = JsonPatchFor[(User, registry)]


@app.patch("/users/{user_id}")
def patch_user(user_id: int, patch: UserPatch = Body(...)) -> User:
    # This endpoint is validated against User + the custom registry.
    user = get_user(user_id)
    return patch.apply(user)
```

**make_json_patch_body(...)** generates a Pydantic RootModel for FastAPI request bodies when
you want typed operations applied to untyped JSON documents.

Example:

```py
from fastapi import Body, FastAPI

from jsonpatch import OperationRegistry, make_json_patch_body
from jsonpatch.types import JSONValue

app = FastAPI()

registry = OperationRegistry.with_standard(ToggleOp)
ConfigPatch = make_json_patch_body(registry, name="ConfigPatch")


@app.patch("/configs/{config_id}")
def patch_config(config_id: str, patch: ConfigPatch = Body(...)) -> JSONValue:
    doc = load_config(config_id)
    return patch.apply(doc)
```

## Non-Goals

- Being the smallest or fastest JSON Patch implementation

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

## Demos (local)

See the comprehensive guide in [`examples/README.md`](./examples/README.md), including:

- Step-by-step FastAPI setup
- curl examples
- Side-by-side comparisons with baseline JSON Patch behavior

## Design philosophy: typed, explicit patch semantics

`JSONPointer[T]` is enforced at runtime

A `JSONPointer[T]` carries an executable type contract:
- `get(doc)` validates that the resolved value is a `T`
- `add(doc, value)` validates that value is a `T` before writing
- `remove(doc)` is intentionally type-gated: the target is resolved and validated
before removal

This prevents accidental schema drift and makes patch behavior explicit.

Examples:
- `JSONPointer[JSONValue]` — permissive (“any JSON value”)
- `JSONPointer[JSONNumber]` — restrictive (“must currently be an int or float, not bool")

If permissive behavior is desired, widen `T` or define a permissive operation
in your registry.

### Covariance is intentional

`JSONPointer[T]` is covariant in `T`.

This allows operations to be composed while preserving guarantees.
For example, a custom operation carrying JSONPointer[JSONBoolean] can delegate
to AddOp without losing boolean-specific enforcement.
