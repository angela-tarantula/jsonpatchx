<h1 align="center">json-patch-x</h1>

<p align="center">
A framework for building <strong>safe and expressive PATCH APIs</strong> in Python.
<br>
Implements JSON Patch as a <strong>first-class API abstraction</strong> with typed operations and FastAPI/OpenAPI support.
<br>
Fully compliant with <a href="https://datatracker.ietf.org/doc/html/rfc6902">RFC 6902</a>, tested against the <a href="https://github.com/json-patch/json-patch-tests">JSON Patch Compliance Test Suite</a>.
</p>


<p align="center">
  <a href="https://github.com/marketplace/actions/super-linter">
    <img src="https://github.com/angela-tarantula/json-patch-x/actions/workflows/python-app.yml/badge.svg?branch=main" alt="CI">
  </a>
</p>


## Overview

**json-patch-x treats `PATCH` as a dialogue, not just a diff.**

In modern distributed systems, a partial update is more than just a document edit. It's a **state transition** that crosses process, service, and trust boundaries. When PATCH becomes a public contract, a mechanical applicator isn’t enough.

json-patch-x turns PATCH into a governed, typed contract:

- Each operation is a **Pydantic model** with explicit semantics
- Pointers are **typed contracts** that fail fast on invalid targets
- Define **custom operations** that encode API meaning directly (`toggle`, `increment`, `replace_substring`, etc.)
- Operations are schemas, so OpenAPI stays in sync **automatically**
- Operations can be **allow-listed per route**
- Plug in your own JSON Pointer implementation for **advanced pointer semantics** (e.g. JSON Path selectors and relative pointers)

The result is PATCH requests that are **predictable**, **reviewable**, and **safe to evolve** without breaking clients.

Here’s what failure looks like when a client targets the wrong type:

```json
{
  "detail": [
    {
      "loc": ["body", 0, "path"],
      "msg": "Pointer type mismatch. Expected JSONBoolean at /active, got JSONString.",
      "type": "jsonpatchx.pointer_type_mismatch"
    }
  ]
}
```

And here’s how easy it is to define and evolve your own operations:

```python
class ReplaceSubstringOp(OperationSchema):
    op: Literal["replace_substring"] = "replace_substring"
    path: JSONPointer[JSONString]
    old: JSONString
    new: JSONString

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        if self.old not in current:
            raise PatchConflictError(f"'{self.old}' is not in '{current}'")
        return ReplaceOp(path=self.path, value=current.replace(self.old, self.new)).apply(doc)
```

Add a feature later? Just extend the schema:

```python
class ReplaceSubstringOp(OperationSchema):
    op: Literal["replace_substring"] = "replace_substring"
    path: JSONPointer[JSONString]
    old: JSONString
    new: JSONString
    strict: JSONBoolean = True

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        if self.strict and self.old not in current:
            raise PatchConflictError(f"strict mode is enabled and '{self.old}' is not in '{current}'")
        return ReplaceOp(path=self.path, value=current.replace(self.old, self.new)).apply(doc)
```

Define your FastAPI route with minimal boilerplate:

```python
from fastapi import FastAPI

app = FastAPI()

UserRegistry = OperationRegistry[AddOp, RemoveOp, ReplaceOp, ReplaceSubstringOp]
UserPatch = JsonPatchFor[User, UserRegistry]

@app.patch("/users/{user_id}")
def patch_user(user_id: str, patch: UserPatch) -> User:
    user = load_user(user_id)
    return patch.apply(user)
```

FastAPI validates the request body against UserRegistry, and OpenAPI documents exactly which operations are allowed.

(assume there's an image of swagger API here)

Want to see it live? Run the [fastapi demos](#demos).


## Fit and Alternatives

json-patch-x is a good fit for:

- **PATCH as a real API contract:** You need safe, expressive, and evolvable operations for your application.
- **Teams generating SDKs or relying on OpenAPI tooling:** Your documentation must reflect exactly which operations are allowed.
- **High-safety or regulated endpoints:** You need strong mutation guarantees and allow-listed operations.
- **Automated or AI-assisted workflows:** Your patches are generated, reviewed, or routed by LLMs or other untrusted tooling.
- **Straightforward RFC 6902 patching:** You just want a correct patch engine without extra ceremony.

But if you primarily need speed or a minimal RFC 6902 applicator and you trust your patches, use [py_yyjson](https://tkte.ch/py_yyjson/#py-yyjson). It's high-performance and also supports JSON Merge Patch ([RFC 7386](https://datatracker.ietf.org/doc/html/rfc7386)) if you prefer "last-write-wins" simplicity.

---

## Table of Contents

- [Core Concepts](#core-concepts)
- [FastAPI Integration](#fastapi-integration)
- [Demos](#demos)
- [Advanced: Pointer Backends](#advanced-pointer-backends)
- [Limitations](#limitations)
- [Contributing](#contributing)

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
at runtime. `JSONPointer[T]` addresses this by enforcing **what** a path may point
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

Why this matters architecturally:

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
AdminRegistry = StandardRegistry
UserRegistry = OperationRegistry[AddOp, MoveOp]

# Extend the language with domain-specific verbs
DevRegistry = OperationRegistry[StandardRegistry, ToggleOp, SwapOp]
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

patch = JsonPatch(patch_ops, registry=DevRegistry)
updated = patch.apply(doc)
```

## FastAPI Integration

FastAPI integration in json-patch-x is built around a simple idea:

> First, define what a patch means. Then, decide how much help you want wiring it into a route.

At the center of this is `JsonPatchFor`, which turns an operation registry into a
**concrete request-body schema** that FastAPI and OpenAPI understand.

### Step 1: Define a Patch Schema with JsonPatchFor

`JsonPatchFor[Model, Registry]` binds three things together:

1. the shape of the document being patched (usually a Pydantic model)
2. the allowed operation vocabulary (an `OperationRegistry`)
3. the JSON Patch execution engine

The result is a Pydantic model that represents a valid PATCH request body.

```py
from jsonpatchx import JsonPatchFor, OperationRegistry, StandardRegistry

UserRegistry = OperationRegistry[StandardRegistry, ToggleOp]
UserPatch = JsonPatchFor[User, UserRegistry]
```

`UserPatch` is a Pydantic model representing a validated list of operations.
It can now be used anywhere FastAPI expects a request body.

### Step 2: Use the Patch Schema in a FastAPI Route

At its simplest, you can plug the patch schema directly into a route:

```py
from fastapi import FastAPI

app = FastAPI()

@app.patch("/users/{user_id}")
def patch_user(user_id: str, patch: UserPatch) -> User:
    user = load_user(user_id)
    return patch.apply(user)
```

With just this:

- FastAPI validates incoming patches against your registry.
- OpenAPI documents exactly which operations are allowed.
- Pointer targets are type-checked at runtime.
- Invalid operations fail *before* any mutation occurs.

No helpers required.

### Step 3: Improving OpenAPI and Content-Type Handling with JsonPatchRoute

`JsonPatchRoute` is an optional helper that keeps your route signature clean
while adding a few niceties:

- `application/json-patch+json` content-type enforcement
- reusable request-body metadata
- examples that stay aligned with your registry

```py
from typing import Annotated, Literal
from fastapi import FastAPI
from jsonpatchx import JsonPatchFor, OperationRegistry, StandardRegistry, JSONValue
from jsonpatchx.fastapi import JsonPatchRoute

app = FastAPI()
UserRegistry = OperationRegistry[StandardRegistry, DeduplicateOp, IncrementOp]
UserPatch = JsonPatchFor[User, UserRegistry]

user_patch = JsonPatchRoute(
    UserPatch,
    examples={
        "increment-balance": {
            "summary": "Increase savings account balance",
            "value": [{"op": "increment", "path": "/accounts/savings/balance", "value": 100}],
        },
    },
    strict_content_type=True,
)

@app.patch(
    "/users/{user_id}",
    **user_patch.route_kwargs(),
)
def patch_user(
    user_id: str,
    patch: Annotated[UserPatch, user_patch.Body()],
) -> User:
    doc = load_user(user_id)
    return patch.apply(doc)
```

Use `JsonPatchRoute` when you want stricter HTTP semantics and richer docs; skip it for a minimal route signature.

### Binding Patches to Pydantic Models vs. Plain JSON

When patching a Pydantic model, use the model type directly:

```py
UserPatch = JsonPatchFor[User, UserRegistry]
```

If you are patching plain JSON documents instead, bind the schema to a named
target using `Literal[...]`:

```py
ConfigPatch = JsonPatchFor[Literal["Database Config"], ConfigRegistry]
```

This name appears in OpenAPI docs and error messages, even though no concrete
model is enforced.

### OpenAPI Customization

Because every operation is a Pydantic model, you can customize titles,
descriptions, and validation logic using standard Pydantic features.

```py
from typing import Literal, Self, override
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

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        val_a, val_b = self.a.get(doc), self.b.get(doc)
        doc = AddOp(path=self.a, value=val_b).apply(doc)
        return AddOp(path=self.b, value=val_a).apply(doc)
```

These details flow automatically into your OpenAPI schema.

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

- **Alternative Syntaxes:** dot-separated paths, [JSONPath](https://www.rfc-editor.org/rfc/rfc9535)-style selectors, or [relative pointers](https://json-schema.org/draft/2020-12/relative-json-pointer).

- **Specialized Escaping:** Domain-specific key encoding or escaping.

- **Contextual Resolution:** Resolving pointers against external state (e.g. database lookups).

- **Path Materialization:** Creating missing segments during traversal instead of failing.

```py
from typing import Any
from jsonpatchx import GenericOperationRegistry, StandardRegistry
from jsonpatchx.backend import PointerBackend

class DotPointer(PointerBackend):
    """A backend for dot-separated paths (e.g., 'metadata.tags.0')."""
    def __init__(self, pointer: str) -> None: ...
    def resolve(self, data: Any) -> Any: ...
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
can call custom helper APIs (e.g., [JsonPath expressions](https://www.rfc-editor.org/rfc/rfc9535), domain-specific helpers, etc).

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

### Limitations

#### FastAPI Validation Context

FastAPI does not yet natively pass `validation_context` from the request body
into Pydantic models, which is required to validate requests against custom
pointer backends.

As a workaround, json-patch-x provides `JsonPatchRoute.dependency()` so
validation runs with the registry context.

```py
from typing import Annotated, Literal

from fastapi import Depends
from jsonpatchx.fastapi import JsonPatchRoute

PatchBody = JsonPatchFor[Literal["DotPointerPatch"], registry]
patch_route = JsonPatchRoute(PatchBody, strict_content_type=True)

@app.patch("/configs/{id}")
def patch_config(
    id: str,
    patch: Annotated[PatchBody, Depends(patch_route.dependency())],
) -> JSONValue:
    # 'patch' is now fully validated using your DotPointer backend
    return patch.apply(load_config(id))
```

Upstream limitation: FastAPI does not expose a request-body validation context today.
See [FastAPI discussion #10864](https://github.com/fastapi/fastapi/discussions/10864).

---

## Contributing

Thank you for your interest in contributing! To get a local copy up and running follow these simple steps.

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

2. Initialize [git submodules](https://git-scm.com/book/en/v2/Git-Tools-Submodules) (required for the external compliance suite)

```sh
git submodule update --init
```

3. Install the dependencies

```sh
uv sync --group dev --all-extras
```

4. Install [prek](https://github.com/j178/prek) (pre-commit runner):

```sh
uv tool install prek
prek install
```

### Development

Run type checks with [mypy](https://www.mypy-lang.org/):

```sh
uv run mypy .
```

Run tests with [pytest](https://docs.pytest.org/en/stable/):

```sh
uv run pytest -v
```

Generate and view the coverage report with [pytest-cov](https://github.com/pytest-dev/pytest-cov):

```sh
uv run pytest --cov=jsonpatchx --cov-report=html
open htmlcov/index.html
```

Lint with [ruff](https://docs.astral.sh/ruff/):

```sh
uv run ruff format
```
