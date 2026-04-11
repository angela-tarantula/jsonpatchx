# Patch Clients

JsonPatchX can validate patch documents client-side before you send them.

## Patch Clients for Standard RFC 6902

For strict RFC 6902 APIs, use `JsonPatch` and organize your client's patching
into 3 stages:

```python
from httpx import Client
from jsonpatchx import JsonPatch

# Stage 1: Build
full_restore = [
    {"op": "copy", "from": "/stats/hp", "path": "/health"},
    {"op": "replace", "path": "/status", "value": "healthy"}
]

# Stage 2: Validate
patch = JsonPatch(full_restore)

# Stage 3: Apply
with Client(base_url="https://api.example.com") as client:
    response = client.patch(
        "/pokemon/pikachu",
        content=patch.to_string(),
        headers={"content-type": "application/json-patch+json"},
    )
    response.raise_for_status()
```

Avoid `list[dict]` boilerplate by using operation models directly:

```python
from jsonpatchx import JsonPatch, CopyOp, ReplaceOp

full_restore = [
    CopyOp(from_="/stats/hp", path="/health"),
    ReplaceOp(path="/status", value="healthy")
]
patch = JsonPatch(full_restore)
```

> Note: `from` is a reserved keyword in Python, so `CopyOp` and `MoveOp` use
> `from_` instead. This is only necessary when you instantiate them directly
> from Python.

When you build patches from operation models, validation errors can be caught
eagerly:

```python
from jsonpatchx import JsonPatch, CopyOp, ReplaceOp

full_restore = [
    CopyOp(from_="/stats/hp", path="health"),  # ERROR: invalid pointer!
    ReplaceOp(path="/status", value="healthy")
]
```

If your client uses prepared JSON patches, use `from_string`:

```python
from pathlib import Path
from jsonpatchx import JsonPatch

patch = JsonPatch.from_string(Path("full_restore_patch.json").read_text())
```

## Patch Clients for Custom PATCH Contracts

When an API service uses JsonPatchX to define custom patch operations, the
cleanest pattern is to publish those operation schemas as importable Python
code, together with the registry alias that matches the PATCH endpoint contract.

For example:

```python
# some_service/patching.py

from .widget_ops import ClampOp, IncrementOp, MultiplyOp

type WidgetPatchRegistry = MultiplyOp | IncrementOp | ClampOp
```

That gives the client one import surface that mirrors the PATCH contract the API
service actually accepts.

With that shared contract, a Python client can build a `JsonPatch` from
instantiated operation schemas, validate it locally, _then_ send it over the
wire:

```python
from httpx import Client
from jsonpatchx import JsonPatch

from some_service.patching import (
    ClampOp,
    IncrementOp,
    MultiplyOp,
    WidgetPatchRegistry,
)

patch = JsonPatch(
    [
        MultiplyOp(path="/foo/bar", scalar=2),
        IncrementOp(path="/foo/bar", amount=20),
        ClampOp(path="/foo/bar", max=100),
    ],
    registry=WidgetPatchRegistry,
)

with Client(base_url="https://api.example.com") as client:
    response = client.patch(
        "/widgets/123",
        content=patch.to_string(),
        headers={"content-type": "application/json-patch+json"},
    )
    response.raise_for_status()
```

> Another advantage of custom operations is that they sidestep stale reads. If a
> client has to read a value, compute a new result locally, and then send a
> final `replace`, that flow is more vulnerable to concurrent updates than
> sending one higher-level operation for the server to apply against current
> state. For example, the above client-side code would succumb to stale reads
> amidst high concurrency under RFC 6902:

```python
from httpx import Client

with Client(base_url="https://api.example.com") as client:
    document = client.get("/users/123").json()
    current = document["foo"]["bar"]

    result = current * 2
    result += 20
    result = min(result, 100)

    patch = JsonPatch(
        [
            {"op": "replace", "path": "/foo/bar", "value": result},
        ]
    )

    response = client.patch(
        "/users/123",
        content=patch.to_string(),
        headers={"content-type": "application/json-patch+json"},
    )
    response.raise_for_status()
```

## What This Changes and What It Doesn't

This is a Python convenience, not a different transport format. The wire
contract is still ordinary JSON Patch.

What changes between these two client styles is where the operation models come
from and where the higher-level mutation logic lives. With strict RFC 6902, the
client imports standard models from JsonPatchX and computes the final value
itself. With custom PATCH contracts, the client imports operation models from
the API service and can send those higher-level operations directly.

## Packaging the Contract

If an API service wants clients to use this pattern, it should expose a stable
import surface for its operation schemas and registry. That can be:

- a public module inside the service package
- a separate shared package published alongside the service
- an internal shared package when both sides live in the same organization

The important part is stability. If client code imports
`some_service.patching.WidgetPatchRegistry`, that import path becomes part of
the contract too.

## Optional Higher-Level Variant

An API service could also publish a ready-made patch request model such as
`JsonPatchFor[...]`, but operation schemas plus a shared registry are usually
the more flexible client surface.
