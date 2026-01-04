# json-patch-x
[![CI](https://github.com/angela-tarantula/json-patch-x/actions/workflows/python-app.yml/badge.svg?branch=main)](https://github.com/marketplace/actions/super-linter)

A typed, schema‑driven PATCH framework for Python, implementing JSON Patch ([RFC 6902](https://datatracker.ietf.org/doc/html/rfc6902)) with extensible operations and first‑class FastAPI/OpenAPI support.

## About

json-patch-x is for teams who need PATCH to be **precise, explainable, and evolvable**.

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
git clone https://github.com/angela-tarantula/json-patch-x
cd json-patch-x
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

op = ReplaceOp(path="/title", value="New")
op = ReplaceOp.model_validate({"op": "replace", "path": "/other/jsonpatch/libraries", "value": True})
```

### Typed JSON Pointers

`JSONPointer[T]` enforces **what** a path may point to, not just **where** it points.
Operations fail loudly if the runtime type contract is violated.

```py
from typing import Literal, override
from jsonpatchx import ReplaceOp, JSONPointer, JSONValue, OperationSchema
from jsonpatchx.types import JSONBoolean

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

#### Covariance

`JSONPointer[T]` is [covariant](https://peps.python.org/pep-0483/#covariance-and-contravariance) in `T` (type-checker concept), so a `JSONPointer[JSONNumber]` can be used where `JSONPointer[JSONValue]` is expected.

Additionally, json-patch-x preserves the pointer's type parameter at runtime, so stricter constraints remain enforced when passed through operations with broader constraints (i.e. a custom op using `JSONPointer[JSONBoolean]` can delegate to `ReplaceOp.apply()` without losing the `JSONBoolean` constraint).

#### JSONPointer is a str

Per [RFC 6901](https://datatracker.ietf.org/doc/html/rfc6901), “a JSON Pointer is a Unicode string”. Modeling it as a `str` is faithful to that definition: `isinstance(pointer, str)` is true, and pointers participate naturally in all string semantics (e.g. `pointer.count("/")`, `"".join([pointer, "/suffix"])`, or `pointer.endswith("/foo")`).

### Operation Registries

An `OperationRegistry` defines:

- which operations are allowed
- how operations are parsed and validated
- which JSON Pointer backend is used ([advanced](#advanced-pointer-backends))

```py
from jsonpatchx import AddOp, MoveOp, OperationRegistry

standard_registry = OperationRegistry.standard()
limited_registry = OperationRegistry(AddOp, MoveOp)
custom_registry = OperationRegistry.with_standard(ToggleOp)
```

The registry is the vocabulary of your PATCH API.

### Applying a Patch

The `JsonPatch` class handles the parsing and execution.

```py
from jsonpatchx import JsonPatch, JSONValue

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
from jsonpatchx import JsonPatchFor, OperationRegistry

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
from jsonpatchx import OperationRegistry, JSONValue, make_json_patch_body

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
from jsonpatchx import AddOp, JSONPointer, JSONValue, OperationSchema, InvalidOperationSchema

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
from jsonpatchx import OperationRegistry
from jsonpatchx.types import PointerBackend


class DotPointer(PointerBackend):
    def __init__(self, pointer: str) -> None: ...
    @property
    def parts(self) -> Sequence[str]: ...
    @classmethod
    def from_parts(cls, parts: Iterable[Any]) -> Self: ...
    def resolve(self, doc: Any) -> Any: ...
    def __str__(self) -> str: ...
    def __hash__(self) -> int: ...


registry = OperationRegistry.with_standard(pointer_cls=DotPointer)
```

This changes pointer parsing and traversal without modifying any operations.

### Backend Access & Binding

- `JSONPointer.ptr` exposes the parsed backend instance for advanced use cases.
- `JSONPointer[T, Backend]` binds a backend at the type level. JSONPointer is also covariant in `Backend`.

Backend selection is still scoped by the registry, allowing different APIs
to use different pointer semantics safely.

### FastAPI Limitation: Validation Context

FastAPI does not currently pass Pydantic validation context for request bodies, which
registry-scoped backends require. Use the provided helper as a workaround:

```py
from fastapi import Depends, FastAPI
from pointerlibrary import DotPointer

from jsonpatchx import JSONValue, OperationRegistry
from jsonpatchx.fastapi import make_json_patch_body_with_dep, JSON_PATCH_MEDIA_TYPE


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
