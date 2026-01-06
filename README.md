# json-patch-x
[![CI](https://github.com/angela-tarantula/json-patch-x/actions/workflows/python-app.yml/badge.svg?branch=main)](https://github.com/marketplace/actions/super-linter)

A typed, schema-driven patching framework for Python. It implements JSON Patch
([RFC 6902](https://datatracker.ietf.org/doc/html/rfc6902)) as a first-class,
extensible **language of intent**, featuring native FastAPI and OpenAPI support.

## Overview

**json-patch-x treats `PATCH` as a dialogue, not just a diff.**

In modern distributed systems, a partial update is more than a document
transformation: it’s a transition between states. Instead of describing updates
only by their final effect, json-patch-x models each operation as a **typed,
validated schema** with explicit semantics.

By shifting the focus from the *outcome* to the *operation*, json-patch-x allows
systems to reason about how data is allowed to evolve, ensuring that every
mutation is precise, explainable, and safe.

---

## Why this exists

Standard JSON Patch implementations are intentionally minimal. They apply
operations mechanically, ignoring the underlying type contracts of your domain.
This simplicity is a liability in systems that require:
- **Strict Governance:** When `PATCH` is a public API contract that must protect complex typed models.
- **Domain Semantics:** When you need to move beyond `add`/`remove` to custom operations like `toggle`, `increment`, or `replace_substring`.
- **Automated Agency:** When patch operations are generated or reviewed by LLMs and automation, requiring validation at the operation boundary to prevent invalid mutations.

json-patch-x bridges the gap between the raw flexibility of RFC 6902 and the
rigid safety of Pydantic.

---

## When to use json-patch-x

- **You maintain "Contract-First" APIs:** You need your OpenAPI docs to accurately reflect allowed patch operations.
- **You need Runtime Type Safety:** You want pointer resolution to fail fast when the target isn't the expected type, instead of silently mutating the wrong type.
- **You use LLMs in your Loop:** You require a structured, validated interface for AI-generated data mutations.
- **You need Auditability:** You care about preserving the "why" (the operation) rather than just the "what" (the change).

## When to use alternatives

**json-patch-x prioritizes correctness, clarity, and extensibility over raw throughput.**
- Use [python-json-patch](https://github.com/stefankoegl/python-json-patch) if you need a minimal, faster applicator for internal state syncing where the input is already trusted.
- Use JSON Merge Patch (RFC 7386) if you prefer the "last-write-wins" simplicity of partial document replacement and don't need to distinguish between `null` assignment and key removal.

## Core Concepts

### Operations as Schemas

In json-patch-x, every operation is a Pydantic model. This elevates a patch
from a "dictionary of strings" to a **validated command**. You get structural
validation, field-level constraints, and clear `apply()` logic in a single,
testable unit.

```py
class ReplaceOp(OperationSchema):
    op: Literal["replace"] = "replace"
    path: JSONPointer[JSONValue]
    value: JSONValue

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        # Internal logic delegates to atomic operations
        doc = RemoveOp(path=self.path).apply(doc)
        return AddOp(path=self.path, value=self.value).apply(doc)
```

### Typed JSON Pointers: The Contract Layer

The most common failure in JSON Patch is a "Path Not Found" or a type mismatch
at runtime. `JSONPointer[T]` solves this by enforcing **what** a path may point
to, not just **where** it points.

By binding a pointer to a type `T`, the operation gains a runtime contract.

```py
from jsonpatchx.types import JSONBoolean

class ToggleOp(OperationSchema):
    op: Literal["toggle"] = "toggle"
    path: JSONPointer[JSONBoolean] # Strict contract: Target MUST be a JSONBoolean

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc) # Returns a JSONBoolean or raises
        return ReplaceOp(path=self.path, value=not current).apply(doc)
```

Why this matters for Architecture:
- **Fail Fast:** Pointer resolution validates target types before mutation.
- **Modular Code:** Operations can be composed of other Operations while preserving type contracts.
- **Self-Documenting Code:** Your type hints tell other developers exactly what structure your patcher expects.
- **Refinement over Time:** You can tighten pointer types in custom ops while keeping the engine unchanged.

### Supported Type Guards

We provide a suite of helper types so you can reason about JSON rather than Python's types:
- `JSONNumber` (`int` or `float`, but explicitly excludes `bool`)
- `JSONString`, `JSONBoolean`, `JSONNull`
- `JSONArray[T]`, `JSONObject[T]`

---

### Operation Registries

An `OperationRegistry` acts as the **vocabulary** of your PATCH API. Instead of
allowing any arbitrary operation, you explicitly define which verbs are "legal"
in your domain.

```py
from jsonpatchx import AddOp, MoveOp, OperationRegistry

# Create a restricted vocabulary for high-security endpoints
admin_registry = OperationRegistry.standard()
user_registry = OperationRegistry(AddOp, MoveOp) 

# Extend the language with domain-specific verbs
custom_registry = OperationRegistry.with_standard(ToggleOp, SwapOp)
```

The registry ensures that your API doesn't just "apply patches"; it speaks your
application's specific language.

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

Most frameworks treat the `PATCH` body as a generic `dict`. This forces clients
to guess which paths and operations are valid. json-patch-x integrates with
FastAPI to export your registry's type constraints directly into your OpenAPI
schema.

### Model-Aware Patching

Use `JsonPatchFor[Model]` when targeting a Pydantic model with the standard registry.

```py
from fastapi import Body, FastAPI
from jsonpatchx import JsonPatchFor

app = FastAPI()
UserPatch = JsonPatchFor[User] # Generates a schema bound to the User model

@app.patch("/users/{user_id}")
def patch_user(user_id: int, patch: UserPatch = Body(...)) -> User:
    user = get_user(user_id)
    # The patched output is revalidated against User's schema
    return patch.apply(user)
```

### The "Registry-to-Schema" Pipeline

By using the `OperationRegistry`, your OpenAPI documentation automatically
reflects your custom vocabulary. If you add a `ToggleOp` or a `SwapOp`, they
appear in the OpenAPI `oneOf` definition for the request body, complete with
descriptions and field constraints.

```py
from jsonpatchx import OperationRegistry, patch_body_for_model

registry = OperationRegistry.with_standard(ConcatenateOp)
# This creates a Pydantic-validated request body that
# knows how to handle 'concatenate' in addition to standard ops.
UserPatch = patch_body_for_model(User, registry=registry)
```

### Plain JSON Patching

You can also use `patch_body_for_json` when you're patching raw JSON (dicts/lists) but you still want that sweet OpenAPI.

```py
from fastapi import Body, FastAPI
from jsonpatchx import OperationRegistry, JSONValue, patch_body_for_json

app = FastAPI()
registry = OperationRegistry.with_standard(DeduplicateOp, IncrementOp)
UserPatch = patch_body_for_json("User", registry=registry)

@app.patch("/configs/{config_id}")
def patch_config(config_id: str, patch: UserPatch = Body(...)) -> JSONValue:
    doc = load_config(config_id)
    return patch.apply(doc)
```

### OpenAPI Customization

Leverage `ConfigDict` and `model_validator` to create sophisticated, well-documented operations.

```py
from typing import Literal, Self
from pydantic import ConfigDict, model_validator
from jsonpatchx import AddOp, JSONPointer, JSONValue, OperationSchema, OperationValidationError

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
            raise OperationValidationError("Paths cannot be prefixes of each other.")
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

Path parsing is pluggable. The default backend follows [RFC 6901](https://datatracker.ietf.org/doc/html/rfc6901), but you can supply your own `PointerBackend` to change how pointers are interpreted.

Custom backends let you implement:
- **Alternative Syntaxes:** `users.0.name` instead of `/users/0/name`, or [relative pointers](https://json-schema.org/draft/2020-12/relative-json-pointer).
- **Specialized Escaping:** Domain-specific key encoding/decoding.
- **Contextual Resolution:** Resolving pointers against external state (e.g. database lookups).
- **Path Materialization:** Creating missing segments during traversal instead of failing.

```py
from jsonpatchx import OperationRegistry
from jsonpatchx.types import PointerBackend

class DotPointer(PointerBackend):
    """A backend for dot-separated paths (e.g., 'metadata.tags.0')."""
    def __init__(self, pointer: str) -> None: ...
    def resolve(self, doc: Any) -> Any: ...
    # ... implement required interface ...

# Bind the backend to a registry
registry = OperationRegistry.with_standard(pointer_cls=DotPointer)
```

### Backend Binding

`JSONPointer[T, Backend]` allows you to bind a specific backend at the type
level, so operations can require a particular pointer syntax when needed.

---

## FastAPI: Bridging the Validation Gap

One architectural hurdle in FastAPI is that it does not natively pass
`validation_context` from the request body into Pydantic models. For
sophisticated pointer backends that require registry-level context,
json-patch-x provides a "dependency bridge" as a workaround.

```py
from jsonpatchx.fastapi import patch_body_for_json_with_dep

# The helper returns a Type and a Dependency to keep FastAPI's DI system happy
PatchBody, PatchDepends, openapi_extra = patch_body_for_json_with_dep(
    "DotPointerPatch",
    registry=registry,
    app=app,
)

@app.patch("/configs/{id}", openapi_extra=openapi_extra)
def patch_config(id: str, patch: PatchBody = Depends(PatchDepends)) -> JSONValue:
    # 'patch' is now fully validated using your DotPointer backend
    return patch.apply(load_config(id))
```

For model-aware patches, use `patch_body_for_model_with_dep`.

```py
from jsonpatchx.fastapi import patch_body_for_model_with_dep

UserPatch, PatchDepends, openapi_extra = patch_body_for_model_with_dep(
    User,
    registry=registry,
    app=app,
)
```

Limitation reference: FastAPI does not expose a request-body validation context today.
See https://github.com/fastapi/fastapi/discussions/10864.

---

# Contributing

Thank you for your interest in contributing!

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
uv sync --group dev --all-extras
```