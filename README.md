# json-patch
[![CI](https://github.com/angela-tarantula/jsonpatch/actions/workflows/python-app.yml/badge.svg?branch=main)](https://github.com/marketplace/actions/super-linter)

A typed JSON Patch (RFC 6902) engine for Python, built for explicit runtime semantics, custom operations,
and clean FastAPI/OpenAPI integration.

## About

json-patch is for teams who need PATCH to be **precise, explainable, and evolvable**.

Typical use cases:

- APIs that accept PATCH requests and must protect typed schemas
- Systems that want explicit, runtime-enforced JSON Pointer semantics
- Teams defining domain-specific patch operations
- FastAPI services that want high-quality OpenAPI schemas for PATCH bodies
- Applications that rely on LLM-generated or LLM-reviewed patch operations

**Non-goal**: This is not a minimal or high-performance patch applicator.

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

## Core concepts (with examples)

### Operations as schemas

Each patch operation is a Pydantic model with explicit fields, validation, and `apply()` semantics.

```py
from typing import Literal, override

from jsonpatch import ReplaceOp
from jsonpatch.schema import OperationSchema
from jsonpatch.types import JSONBoolean, JSONPointer, JSONValue


class ToggleOp(OperationSchema):
    op: Literal["toggle"] = "toggle"
    path: JSONPointer[JSONBoolean]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        return ReplaceOp(path=self.path, value=not current).apply(doc)
```

Operations fail **loudly and eagerly** when contracts are violated.

### Typed JSON Pointers

`JSONPointer[T]` enforces *what* a path may point to, not just *where* it points.
Operations fail loudly when the runtime type contract is violated.

```py
from typing import Literal

from jsonpatch.schema import OperationSchema
from jsonpatch.types import JSONNumber, JSONPointer


class ReplaceNumber(OperationSchema):
    op: Literal["replace_number"] = "replace_number"
    path: JSONPointer[JSONNumber]
    value: JSONNumber

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        return ReplaceOp(path=self.path, value=self.value).apply(doc)
```

At runtime:

- `get(doc)` validates the resolved value is a `T`
- `add(doc, value)` validates the value before writing
- `remove(doc)` validates the target before removal

Helper types are provided to let you reason about JSON, not Python:

- `JSONBoolean`
- `JSONNumber` (excludes bool)
- `JSONString`
- `JSONNull`
- `JSONArray[T]`
- `JSONObject[T]`
- `JSONValue` (any JSON value)

`JSONPointer[T]` is covariant in `T`, so composed operations can preserve strict pointer guarantees.

### Operation registries

An `OperationRegistry` defines:

- which operations are allowed
- how operations are parsed and validated
- which JSON Pointer backend is used ([advanced](./README.md#advanced-custom-pointer-backends))

Registries are explicit, immutable, and composable.

```py
from jsonpatch import AddOp, MoveOp, OperationRegistry

standard_registry = OperationRegistry.standard()
limited_registry = OperationRegistry(AddOp, MoveOp)
custom_registry = OperationRegistry.with_standard(ToggleOp)
```

The registry is the vocabulary of your PATCH API.

### Applying a patch

`JsonPatch` parses and applies a patch document to a JSON value.

```py
from jsonpatch import JsonPatch
from jsonpatch.types import JSONValue

doc = {"title": "Example", "trial": False}

patch_ops = [
    {"op": "replace", "path": "/foo", "value": "bar"},
    {"op": "remove", "path": "/baz"}
]

patch = JsonPatch(patch_ops, registry=my_registry)
updated = patch.apply(doc)
```

Operations may be provided as raw dicts or as instantiated operation models:

```py
patch_ops = [ReplaceOp(path="/foo", value="bar"), RemoveOp(path="/baz")]
```

### FastAPI integration

`JsonPatchFor[Model]` generates a Pydantic RootModel for patching a specific BaseModel
and validates the patched output back into that model.

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

The OpenAPI schema for the PATCH body reflects the allowed operations and their fields.

### Untyped JSON patching

For untyped JSON documents, use `make_json_patch_body`.

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

## Error semantics

- Pointer resolution errors fail immediately
- Type violations fail immediately
- Operations are applied sequentially and fail-fast
- Partial application does not occur

Errors are explicit by design.

## Advanced: pointer backends

The engine is JSON Pointer backend-agnostic.

To support alternative semantics (dot notation, custom escaping, relative pointers),
implement `PointerBackend` and supply it to a registry.

```py
from jsonpatch import OperationRegistry
from jsonpatch.types import PointerBackend


class DotPointer(PointerBackend):
    def __init__(self, pointer: str) -> None: ...
    @property
    def parts(self): ...
    @classmethod
    def from_parts(cls, parts): ...
    def resolve(self, doc): ...
    def __str__(self) -> str: ...


registry = OperationRegistry.with_standard(pointer_cls=DotPointer)
```

This changes pointer parsing and traversal without modifying any operations.

### Backend access & binding

- `JSONPointer.ptr` exposes the parsed backend instance for advanced use cases
- `JSONPointer[T, Backend]` binds a backend at the type level

Backend selection is still scoped by the registry, allowing different APIs
to use different pointer semantics safely.

## Demos

See [`examples/README.md`](./examples/README.md) for the FastAPI demo suite, including:

- typed model patching
- untyped JSON patching
- custom operations
- model-bound custom operations
- custom JSON pointer backends