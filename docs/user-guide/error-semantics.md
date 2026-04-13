# Error Semantics

A governed PATCH API is defined just as much by how it fails as by how it
mutates.

If the route has stable success behavior but fuzzy failure behavior, the
contract is still incomplete.

## Decide Your Status Mapping on Purpose

With the optional FastAPI helper layer installed, a good default mapping looks
like this:

| HTTP status | Meaning                                                                                                                                      |
| ----------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `415`       | the route requires `application/json-patch+json` and the request used the wrong media type                                                   |
| `422`       | the request body is not a valid patch document, uses a disallowed operation, or produces a patched result that fails target-model validation |
| `409`       | the patch is valid but cannot be applied to the current resource state                                                                       |
| `500`       | the server hit an unexpected patch execution failure or route misconfiguration                                                               |

That mapping works well because it keeps three different failure modes separate:

- request contract failures
- current-state conflicts
- server mistakes

If you do not use the helper layer, choose an equivalent mapping and keep it
stable.

## Install the Helper Layer Once

```python
from fastapi import FastAPI

from jsonpatchx.fastapi import install_jsonpatch_error_handlers


app = FastAPI()
install_jsonpatch_error_handlers(app)
```

The point is not only convenience. It is keeping PATCH failures consistent
across routes.

## Disallowed Operations Should Fail at Parse Time

When a route accepts a registry-limited contract, an unsupported operation
should fail before mutation runs.

If a public route does not advertise `test` or `increment`, the client has not
sent a business-rule violation. It has sent a request body that does not match
the route contract.

Treat that as a request validation failure.

## Keep the Error Response Shape Stable

A good PATCH contract keeps the shape of failures predictable.

A small client-facing response can stay simple:

```json
{ "detail": "patched value failed validation" }
```

And a more operator-friendly failure can include structured detail when that is
useful:

```json
{
  "detail": {
    "index": 2,
    "op": { "op": "replace", "path": "/email", "value": 42 },
    "message": "patched value failed validation",
    "cause_type": "ValidationError"
  }
}
```

The exact wording of the message can evolve more freely than the shape and
status mapping.

Clients usually care most about:

- which status code category they got
- whether `detail` is a string or an object
- whether the route keeps those choices stable over time

## Stable Failures Make Richer PATCH Practical

This matters even more once you introduce custom operations and selector-style
targeting.

The more expressive the contract gets, the more important it is that failures
stay predictable.

That is how richer PATCH APIs stop feeling experimental and start feeling
dependable.
