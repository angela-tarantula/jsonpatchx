# About

JsonPatchX starts with RFC 6902 JSON Patch and goes farther when an API needs
more than a generic patch document.

If all you want is standard JSON Patch, you can use `JsonPatch` and stop there.
It is Pydantic-backed, standards-compliant, and intentionally easy to reach.

If PATCH is part of a public API contract, JsonPatchX gives you more structure:
typed request models, validation before mutation, target-model revalidation
after mutation, OpenAPI generated from the same operation models, and
route-level control over which operations each endpoint accepts.

```python
from jsonpatchx import JsonPatch, JsonPatchFor

patch = JsonPatch(
    [
        {"op": "replace", "path": "/status", "value": "active"},
    ]
)

UserPatch = JsonPatchFor[User]
```

That second line is the center of the project. It keeps JSON Patch on the wire,
but turns the body into an explicit API contract.

## What changes when PATCH becomes a contract

Once PATCH is part of an API surface, you usually care about things like:

- whether the request body is validated before mutation
- whether the patched result is validated as the target model
- whether OpenAPI matches what the route actually accepts
- whether one endpoint should accept a smaller mutation vocabulary than another
- whether repeated domain mutations should have their own named operations
- whether exact-path addressing is enough, or query-style targeting would be
  clearer

That is the contract layer JsonPatchX adds.

It is still JSON Patch at the bottom. The difference is that the patch layer
stops being anonymous.

## You do not have to buy into the whole vision

The User Guide starts with plain RFC 6902 because that keeps the moving parts
small. That is a learning path, not a demand.

You can use JsonPatchX in layers:

- use `JsonPatch` for plain standard JSON Patch
- use `JsonPatchFor[Target]` when PATCH becomes part of a FastAPI contract
- use `JsonPatchFor[Target, Registry]` when different endpoints or environments
  need different operation sets
- add custom operations or `JSONSelector` only where the domain really needs
  them

That progression matters. JsonPatchX should feel usable on day one even if you
never adopt the whole idea.

## Where this is heading

JSON Patch has stayed deliberately small for a long time.
[JSONPath](https://datatracker.ietf.org/doc/html/rfc9535) now has a standard.
That makes this a good moment to experiment with richer PATCH contracts without
throwing away the RFC core.

JsonPatchX is meant to be a serious place to do that.

Keep standard JSON Patch easy. Keep extensions explicit. Try better targeting,
better operation semantics, and better governance in production-sized systems.
Let the good ideas survive.
