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

Non-goal: This is not a minimal or high-performance patch applicator.

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
git clone https://github.com/angela-tarantula/jsonpatch
cd jsonpatch
```

2. Install the dependencies

```sh
uv sync
```

## Core Concepts

### Operations as Schemas

Each operation is a Pydantic model. This means you get explicit fields, validation, and clear `apply()` semantics out of the box.

```py
class ReplaceOp(OperationSchema):
    op: Literal["replace"] = "replace"
    path: JSONPointer[JSONValue]
    value: JSONValue

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        doc = RemoveOp(path=self.path).apply(doc)
        return AddOp(path=self.path, value=self.value).apply(doc)
```

### Typed JSON Pointers

`JSONPointer[T]` enforces **what** a path may point to, not just **where** it points.
Operations fail loudly if the runtime type contract is violated.

```py
from typing import Literal, override
from jsonpatch import ReplaceOp
from jsonpatch.schema import OperationSchema
from jsonpatch.types import JSONBoolean, JSONPointer, JSONValue

class ToggleOp(OperationSchema):
    op: Literal["toggle"] = "toggle"
    path: JSONPointer[JSONBoolean]  # Path MUST point to a boolean

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc) # Returns a JSONBoolean
        return ReplaceOp(path=self.path, value=not current).apply(doc)
```

At runtime:

- `get(doc)` validates the resolved value matches type `T`
- `add(doc, value)` validates the value before writing
- `remove(doc)` validates the value before removal

#### Supported Helper Types

These types allow you to reason about JSON structure rather than Python primitives:

- `JSONBoolean` 
- `JSONNumber` (excludes bool)
- `JSONString`
- `JSONNull`
- `JSONArray[T]`
- `JSONObject[T]`
- `JSONValue` (any JSON value)

`JSONPointer[T]` is **covariant**, meaning stricter types survive composition. If a custom op uses a
`JSONPointer[JSONBoolean]`, it maintains that numeric constraint even when passed to a generic `ReplaceOp`.

Additional JSONPointer helpers:

- `parts`: Access unescaped pointer path tokens
- `type_param`: Inspect the pointer's expected type
- `is_root()`: Check if the pointer is the document root
- `is_parent_of(other)`: Check for pointer ancestry
- `is_gettable(doc)`: Safety check before resolution
- `is_addable(doc, value=..., validate_value=True)`: Safety check before modification

### Operation Registries

An `OperationRegistry` defines:

- which operations are allowed
- how operations are parsed and validated
- which JSON Pointer backend is used ([advanced](#advanced-pointer-backends))

```py
from jsonpatch import AddOp, MoveOp, OperationRegistry

standard_registry = OperationRegistry.standard()
limited_registry = OperationRegistry(AddOp, MoveOp)
custom_registry = OperationRegistry.with_standard(ToggleOp)
```

The registry is the vocabulary of your PATCH API.

### Applying a Patch

The `JsonPatch` class handles the parsing and execution.

```py
from jsonpatch import JsonPatch
from jsonpatch.types import JSONValue

doc = {"title": "Example", "active": False}

# 1. Using dictionaries
patch_ops = [{"op": "replace", "path": "/title", "value": "Updated"}]

# 2. Using instantiated models
# patch_ops = [ReplaceOp(path="/title", value="Updated")]

# 3. From a JSON string
# patch = JsonPatch.from_string('[{"op": "toggle", "path": "/active"}]')

patch = JsonPatch(patch_ops, registry=custom_registry)
updated = patch.apply(doc)
```

## Framework Integration (FastAPI/OpenAPI)

### Model-Aware Patching

Use `JsonPatchFor[Model]` when targeting a Pydantic model. This generates a `RootModel`
bound to that model, ensuring your OpenAPI documentation reflects the specific schema.

```py
from fastapi import Body, FastAPI
from jsonpatch import JsonPatchFor, OperationRegistry

app = FastAPI()
registry = OperationRegistry.with_standard(ConcatenateOp)
UserPatch = JsonPatchFor[User, registry]

@app.patch("/users/{user_id}")
def patch_user(user_id: int, patch: UserPatch = Body(...)) -> User:
    user = get_user(user_id)
    return patch.apply(user)
```

### Plain JSON Patching

Use `make_json_patch_body` when patching raw JSON (dicts/lists) rather than models.

```py
from fastapi import Body, FastAPI
from jsonpatch import OperationRegistry, make_json_patch_body
from jsonpatch.types import JSONValue

app = FastAPI()
registry = OperationRegistry.with_standard(DeduplicateOp, IncrementOp)
CustomPatch = make_json_patch_body(registry, name="CustomConfig")

@app.patch("/configs/{config_id}")
def patch_config(config_id: str, patch: CustomPatch = Body(...)) -> JSONValue:
    doc = load_config(config_id)
    return patch.apply(doc)
```

### OpenAPI Customization

Leverage `ConfigDict` and `model_validator` to create sophisticated, well-documented operations.

```py
from typing import Literal, Self
from pydantic import ConfigDict, model_validator
from jsonpatch import AddOp, InvalidOperationSchema, JSONValue, OperationSchema
from jsonpatch.types import JSONPointer


class SwapOp(OperationSchema):
    model_config = ConfigDict(
        title="Swap operation",
        json_schema_extra={"description": "Swaps values at paths a and b."}
    )
    op: Literal["swap"] = "swap"
    a: JSONPointer[JSONValue]
    b: JSONPointer[JSONValue]

    @model_validator(mode="after")
    def _reject_proper_prefixes(self) -> Self:
        if self.a.is_parent_of(self.b) or self.b.is_parent_of(self.a):
            raise InvalidOperationSchema("Paths cannot be prefixes of each other.")
        return self

    def apply(self, doc: JSONValue) -> JSONValue:
        val_a, val_b = self.a.get(doc), self.b.get(doc)
        doc = AddOp(path=self.a, value=val_b).apply(doc)
        return AddOp(path=self.b, value=val_a).apply(doc)
```

## Demos

See [`examples/README.md`](./examples/README.md) for the FastAPI demo suite, including:

- typed model patching
- model-bound custom ops
- custom operations on JSON documents
- pointer backends with context injection


## Advanced: Pointer Backends

The engine is JSON Pointer backend-agnostic.

To support alternative semantics (dot notation, custom escaping, relative pointers, etc),
implement `PointerBackend` and supply it to a registry.

```py
from jsonpatch import OperationRegistry
from jsonpatch.types import PointerBackend


class DotPointer(PointerBackend):
    def __init__(self, pointer): ...
    @property
    def parts(self):...
    @classmethod
    def from_parts(cls, parts): ...
    def resolve(self, doc): ...
    def __str__(self): ...


registry = OperationRegistry.with_standard(pointer_cls=DotPointer)
```

This changes pointer parsing and traversal without modifying any operations.

### Backend Access & Binding

- `JSONPointer.ptr` exposes the parsed backend instance for advanced use cases
- `JSONPointer[T, Backend]` binds a backend at the type level

Backend selection is still scoped by the registry, allowing different APIs
to use different pointer semantics safely.

### FastAPI Limitation: Validation Context

FastAPI does not currently pass Pydantic validation context for request bodies, which
registry-scoped backends require. Use the provided helper as a workaround:

> NOTE: Features in jsonpatch.fastapi are currently considered unstable.

```py
from fastapi import Depends, FastAPI
from pointerlibrary import DotPointer

from jsonpatch import OperationRegistry
from jsonpatch.types import JSONValue
from jsonpatch.fastapi import make_json_patch_body_with_dep, JSON_PATCH_MEDIA_TYPE


app = FastAPI()
registry = OperationRegistry.with_standard(pointer_cls=DotPointer)

PatchBody, PatchDepends, openapi_extra = make_json_patch_body_with_dep(
    registry,
    name="DotPointer",
    media_type=JSON_PATCH_MEDIA_TYPE,
    app=app,
)

@app.patch("/configs/{id}", openapi_extra=openapi_extra)
def patch_config(id: str, patch: PatchBody = Depends(PatchDepends)) -> JSONValue:
    return patch.apply(load_config(id))
```

Limitation reference: FastAPI does not expose a request-body validation context today.
See https://github.com/fastapi/fastapi/discussions/10864.