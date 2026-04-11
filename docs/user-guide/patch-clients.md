# Patch Clients

If the API service publishes its patch operation models as importable Python
code, a Python client can use the same operation classes to construct valid
patch documents instead of hand-writing `dict`s.

On this page, `API service` means the Python package that owns the PATCH
endpoint and its operation schemas. The `server` is the runtime that exposes
that contract over HTTP, but the importable contract usually lives in the
service package.

## Patch Clients for Custom PATCH Contracts

When an API service defines custom patch operations, the cleanest pattern is to
publish those operation schemas as importable Python code.

### Export a Shared Contract

The cleanest pattern is for the API service to expose two things:

- the operation schemas it accepts
- a registry alias that matches the PATCH endpoint contract

For example:

```python
# some_service/patching.py

from .widget_ops import ClampOp, IncrementOp, MultiplyOp

type WidgetPatchRegistry = MultiplyOp | IncrementOp | ClampOp
```

That gives the client one import surface that mirrors the PATCH contract the API
service actually accepts.

### Build and Send the Patch

With that shared contract, a Python client can build a `JsonPatch` from
instantiated operation schemas, validate it locally, and send the ordinary JSON
Patch wire format with `httpx`:

```python
from httpx import Client

from some_service.patching import (
    ClampOp,
    IncrementOp,
    MultiplyOp,
    WidgetPatchRegistry,
)
from jsonpatchx import JsonPatch

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

The shared registry matters because it keeps the client's local validation
aligned with the API service's accepted operations. If the client tries to send
an operation outside `WidgetPatchRegistry`, that mismatch is caught before the
request goes over the wire.

## Patch Clients for Standard RFC 6902

If an API service adheres strictly to RFC 6902 JSON Patch, a Python client can
still use typed operation models. It just imports the standard ones from
JsonPatchX itself instead of from the API service package.

In that setup, the client still sends a JSON Patch document, but any higher-
level mutation logic lives on the client-side. For example, if the client wants
to multiply a value by `2`, add `20`, clamp it to `100`, and then send the
result, the client has to do that work before it emits the final `replace`:

```python
from httpx import Client
from jsonpatchx import JsonPatch, ReplaceOp

with Client(base_url="https://api.example.com") as client:
    document = client.get("/users/123").json()
    current = document["foo"]["bar"]

    result = current * 2
    result += 20
    result = min(result, 100)

    patch = JsonPatch(
        [
            ReplaceOp(path="/foo/bar", value=result),
        ]
    )

    response = client.patch(
        "/users/123",
        content=patch.to_string(),
        headers={"content-type": "application/json-patch+json"},
    )
    response.raise_for_status()
```

This is still a patch client. The difference is where the operation models come
from and where the multiply/add/clamp logic lives.

For custom PATCH contracts, a Python client can import the API service's shared
operation models and send those higher-level operations directly. For strict RFC
6902 JSON Patch, it can import the standard operation models from JsonPatchX
itself.

## What This Changes and What It Doesn't

This is a Python convenience, not a different transport format. The wire
contract is still ordinary JSON Patch.

What changes is where the client gets its operation models:

- from the API service for custom PATCH contracts
- from JsonPatchX for strict RFC 6902 contracts

In both cases, the client is still constructing and sending a JSON Patch
document.

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
