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

## Table of Contents

- [Why this exists](#why-this-exists)
- [When to use json-patch-x](#when-to-use-json-patch-x)
- [When to use alternatives](#when-to-use-alternatives)
- [Core Concepts](#core-concepts)
- [Framework Integration (FastAPI/OpenAPI)](#framework-integration-fastapiopenapi)
- [Demos](#demos)
- [Advanced: Pointer Backends](#advanced-pointer-backends)
- [Limitations](#limitations)
- [Contributing](#contributing)

## Why this exists

Standard JSON Patch implementations are intentionally minimal. They apply
operations mechanically, ignoring the underlying type contracts of your domain.
This simplicity is a liability in systems that require:
- **Strict Governance:** When `PATCH` is a public API contract that must protect complex typed models.
- **Domain Semantics:** When you need to move beyond `add`/`remove` to custom operations like `toggle`, `increment`, or `replace_substring`.
- **Automated Agency:** When patch operations are generated or reviewed by LLMs and automation, requiring validation at the operation boundary to prevent invalid mutations.

json-patch-x bridges the gap between the raw flexibility of RFC 6902 and the
rigid safety of Pydantic.

## When to use json-patch-x

- **You maintain "Contract-First" APIs:** You need your OpenAPI docs to accurately reflect allowed patch operations.
- **You need Runtime Type Safety:** You want pointer resolution to fail fast when the target isn't the expected type, instead of silently mutating the wrong type.
- **You use LLMs in your Loop:** You require a structured, validated interface for AI-generated data mutations.
- **You need Auditability:** You care about preserving the "why" (the operation) rather than just the "what" (the change).

## When to use alternatives

**json-patch-x prioritizes correctness, clarity, and extensibility over raw throughput.**
- Use [python-json-patch](https://github.com/stefankoegl/python-json-patch) if you need a minimal, faster applicator for internal state syncing where the patch is already trusted.
- Use JSON Merge Patch ([RFC 7386](https://datatracker.ietf.org/doc/html/rfc7386)) if you prefer the "last-write-wins" simplicity of partial document replacement and don't need to distinguish between `null` assignment and key removal.

---

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
- `JSONValue`

### Operation Registries

An `OperationRegistry` acts as the **vocabulary** of your PATCH API. Instead of
allowing any arbitrary operation, you explicitly define which verbs are "legal"
in your domain.

```py
from jsonpatchx import AddOp, MoveOp, OperationRegistry, StandardRegistry

# Create a restricted vocabulary for high-security endpoints
admin_registry = StandardRegistry
user_registry = OperationRegistry[AddOp, MoveOp]

# Extend the language with domain-specific verbs
dev_registry = OperationRegistry[StandardRegistry, ToggleOp, SwapOp]
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

Use `JsonPatchFor[Model, Registry]` when targeting a Pydantic model with an OperationRegistry.

```py
from fastapi import Body, FastAPI
from jsonpatchx import JsonPatchFor, OperationRegistry, StandardRegistry

app = FastAPI()
UserRegistry = OperationRegistry[StandardRegistry, ConcatenateOp]
UserPatch = JsonPatchFor[User, UserRegistry] # Generates a schema bound to the User model

@app.patch("/users/{user_id}")
def patch_user(user_id: int, patch: UserPatch = Body(...)) -> User:
    user = get_user(user_id)
    # The patched output is revalidated against User's schema
    return patch.apply(user)
```

### Plain JSON Patching

You can also use `JsonPatchFor[Literal["Name"], Registry]` when you're patching raw JSON (dicts/lists) but you still want that sweet OpenAPI.

```py
from fastapi import Body, FastAPI
from jsonpatchx import JsonPatchFor, OperationRegistry, StandardRegistry, JSONValue

app = FastAPI()
ConfigRegistry = OperationRegistry[StandardRegistry, DeduplicateOp, IncrementOp]
ConfigPatch = JsonPatchFor[Literal["Database Config"], ConfigRegistry]

@app.patch("/configs/{config_id}")
def patch_config(config_id: str, patch: ConfigPatch = Body(...)) -> JSONValue:
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

---

## Demos

See [`examples/recipes.py`](./examples/recipes.py) for a catalog of custom operation recipes.

See [`examples/fastapi/README.md`](./examples/fastapi/README.md) for the FastAPI demo suite, including:

- typed model patching
- model-bound custom ops
- custom operations on JSON documents
- pointer backends with context injection

---

## Advanced: Pointer Backends

Path parsing is pluggable. The default backend follows [RFC 6901](https://datatracker.ietf.org/doc/html/rfc6901), but you can supply your own `PointerBackend` to change how pointers are interpreted.

Custom backends let you implement:
- **Alternative Syntaxes:** `users.0.name` instead of `/users/0/name`, or [relative pointers](https://json-schema.org/draft/2020-12/relative-json-pointer).
- **Specialized Escaping:** Domain-specific key encoding/decoding.
- **Contextual Resolution:** Resolving pointers against external state (e.g. database lookups).
- **Path Materialization:** Creating missing segments during traversal instead of failing.

```py
from typing import Any
from jsonpatchx import GenericOperationRegistry, StandardRegistry
from jsonpatchx.types import PointerBackend

class DotPointer(PointerBackend):
    """A backend for dot-separated paths (e.g., 'metadata.tags.0')."""
    def __init__(self, pointer: str) -> None: ...
    def resolve(self, doc: Any) -> Any: ...
    # ... implement required interface ...

# Bind the backend to a registry
registry = GenericOperationRegistry[StandardRegistry, ToggleOp, DotPointer]
```

The last param of `GenericOperationRegistry` must be the custom pointer class.

An `OperationRegistry` is just a `GenericOperationRegistry` with a default PointerBackend.

### Backend Binding

`JSONPointer[T, Backend]` allows you to bind a specific backend at the type
level, so operations can require a particular pointer syntax when needed.
For advanced use cases, `JSONPointer.ptr` exposes the backend instance so you
can call custom helper APIs (e.g., wildcard expansion, JsonPath expressions, etc).

```py
from typing import Literal
from jsonpatchx import JSONPointer, JSONValue, OperationSchema, ReplaceOp
from your-next-OS-project import JsonPathPointer

class JsonPathReplaceOp(OperationSchema):
    op: Literal["jsonpath_replace"] = "jsonpath_replace"
    path: JSONPointer[JSONValue, JsonPathPointer]
    value: JSONValue

    def apply(self, doc: JSONValue) -> JSONValue:
        # JsonPathPointer could expose richer APIs (e.g. resolve_jsonpath) for multi-target ops
        targets = self.path.ptr.resolve_jsonpath(doc)
        for target in targets:
            ReplaceOp(path=target, value=self.value).apply(doc)
        return doc
```

Ops that require a custom pointer backend can only live in registries that bind
that backend for all ops.

See [FastAPI Validation Context](#fastapi-validation-context) for the FastAPI
request-body validation workaround.

---

# Limitations

## JSONValue Type System

### Short version (you just want to plug‑and‑play)

Python’s type system treats `list`/`dict` as invariant, so it can’t accept that
`JSONArray[JSONNumber]` is a `JSONValue`, even though it is valid JSON. This can
surface as **mypy errors** on `JSONPointer[JSONArray[JSONNumber]]` and similar types.

**Workaround:** use a targeted ignore on the pointer annotation:

```py
path: JSONPointer[JSONArray[JSONNumber]]  # type: ignore[type-var]
```

This keeps runtime behavior correct while acknowledging a typing limitation.

### Long version (why this happens)

`JSONValue` is defined recursively:

```py
type JSONValue = JSONPrimitive | JSONArray[JSONValue] | JSONObject[JSONValue]
```

Semantically, a list of numbers is a JSON value. But in Python typing,
`list[T]` and `dict[K, V]` are **invariant**. That means:

- `list[JSONNumber]` is **not** a subtype of `list[JSONValue]`
- therefore `JSONArray[JSONNumber]` is **not** a subtype of `JSONArray[JSONValue]`
- therefore `JSONPointer[JSONArray[JSONNumber]]` is rejected when the type
  parameter is bounded to `JSONValue`

There is not currently a way to define `JSONValue` such that `JSONArray[JSONValue]`
and `JSONObject[JSONValue]` are understood **recursively**.

**Why not use `Sequence`/`Mapping`?** Those are covariant but read‑only; JSON
Patch mutates arrays/objects, so modeling arrays as read‑only would be an
incorrect API contract and would force casts or copies everywhere.

**Current guidance:** Keep the runtime model honest and use a targeted `# type: ignore`
on pointer annotations that need narrower array/object types. If anyone is interesting
in mentoring me to submit a PEP to improve Python's type system, please reach out!

## FastAPI Validation Context

FastAPI does not yet natively pass `validation_context` from
the request body into Pydantic models, which is required to validate
requests against your custom backend.

As a workaround, json-patch-x provides a `PatchDependency`.

```py
from fastapi import Body, Depends
from jsonpatchx.fastapi import PatchDependency

PatchBody = JsonPatchFor["DotPointerPatch", registry]
PatchDepends = PatchDependency(
    PatchBody,
    app=app,
    request_param=Body(..., media_type="application/json-patch+json"),
)

@app.patch("/configs/{id}")
def patch_config(id: str, patch: PatchBody = Depends(PatchDepends)) -> JSONValue:
    # 'patch' is now fully validated using your DotPointer backend
    return patch.apply(load_config(id))
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
