# Patch Clients

JsonPatchX can validate patch documents client-side before you send them.

## Patch Clients for Standard RFC 6902

A simple RFC 6902 patch client usually has three steps:

```python
from httpx import Client
from jsonpatchx import JsonPatch

# Step 1: Build
full_restore = [
    {"op": "copy", "from": "/stats/hp", "path": "/health"},
    {"op": "replace", "path": "/status", "value": "healthy"}
]

# Step 2: Validate
patch = JsonPatch(full_restore)

# Step 3: Send
with Client(base_url="https://api.example.com") as client:
    response = client.patch(
        "/pokemon/pikachu",
        content=patch.to_string(),
        headers={"content-type": "application/json-patch+json"},
    )
    response.raise_for_status()
```

### Model-Based Patches

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
> `from_` instead. This is only necessary when you instantiate them directly.

When you build patches from operation models, validation errors can be caught
eagerly:

```python
from jsonpatchx import JsonPatch, CopyOp, ReplaceOp

full_restore = [
    CopyOp(from_="/stats/hp", path="health"),  # ERROR: invalid pointer!
    ReplaceOp(path="/status", value="healthy")
]
```

### Prepared Patches

If your client uses prepared JSON patches, use `from_string`:

```python
from pathlib import Path
from jsonpatchx import JsonPatch

patch = JsonPatch.from_string(Path("full_restore_patch.json").read_text())
```

## Patch Clients for Custom PATCH Contracts

If an API service defines custom patch operations with JsonPatchX, it can
publish those operation schemas together with the registry alias that matches
the PATCH endpoint contract.

For example:

```python
# some_service/patching.py

from .widget_ops import ClampOp, IncrementOp, MultiplyOp

type WidgetPatchRegistry = MultiplyOp | IncrementOp | ClampOp
```

That gives clients one import surface that mirrors the contract the API service
actually accepts. Keep that surface stable. It can live in:

- a public module inside the service package
- a separate shared package published alongside the service
- an internal shared package when both sides live in the same organization

With that shared contract, a Python client can build a `JsonPatch`, validate it
locally, then send it:

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

`registry=WidgetPatchRegistry` keeps client-side validation aligned with the
operations the API service actually accepts. This is still ordinary JSON Patch
on the wire.

For why this pattern is especially useful for agents, see
[Agentic Patching](agentic-patching.md).
