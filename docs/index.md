# JsonPatchX

A PATCH framework for Python.

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

## Why this exists

[RFC 6902](https://datatracker.ietf.org/doc/html/rfc6902) is good at what it set
out to do. It gives you a standard document format for a sequence of patch
operations and a media type for sending them over HTTP.

That still leaves a lot of practical API design questions open.

Many teams react by avoiding PATCH, or by using
[JSON Merge Patch](https://datatracker.ietf.org/doc/html/rfc7386) when updates
are simple enough that “just send the new object shape” feels easier. That is a
reasonable trade-off a lot of the time. Merge Patch is a good fit for coarse
object updates where array handling, explicit deletions, and per-operation
semantics do not matter much.

JsonPatchX is for the cases where they do.

Those cases show up quickly in real systems. Browser clients, internal tools,
third-party integrations, and increasingly LLM-generated patches all cross trust
boundaries. At that point, a route usually needs more than “send me a list of
patch dicts and I’ll try to apply them.”

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

## Why not just use Merge Patch

Merge Patch stays attractive because it is simple to explain and simple to
generate. For some APIs, that simplicity wins.

But it comes with different trade-offs. It is much less explicit about mutation
intent. It gets awkward once arrays matter. It is not a good fit when you want
operation-level policy, extension, or stable error semantics around specific
kinds of mutations.

JsonPatchX is not trying to replace Merge Patch everywhere. It is for APIs that
want the precision of patch operations, plus a cleaner way to govern them.

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

The next page gets you running with plain `JsonPatch` and then the smallest
possible `JsonPatchFor[...]` route.
