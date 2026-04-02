# JsonPatchX

JsonPatchX is a Python library for PATCH APIs.

At the bottom, it is a clean implementation of
[RFC 6902](https://datatracker.ietf.org/doc/html/rfc6902) JSON Patch. You can
parse a standard patch document, apply it to JSON, and stop there.

The reason the project exists, though, is that most real PATCH endpoints need
more than transport semantics. They need request models. They need validation
before mutation. They need OpenAPI that matches what the route will really
accept. They need a way to say that one client may send `replace`, while another
may also send `increment`. JsonPatchX adds that contract layer without throwing
away JSON Patch.

If all you want is standards-compliant JSON Patch, JsonPatchX welcomes that use
case first. If you want governed PATCH APIs, it gives you a path there.

```python
from jsonpatchx import JsonPatch, JsonPatchFor, StandardRegistry

# 1) Plain RFC 6902 patching
patch = JsonPatch(
    [
        {"op": "replace", "path": "/tier", "value": "pro"},
        {"op": "add", "path": "/features/-", "value": "priority-support"},
    ]
)

# 2) The same RFC operation set, now as an API contract
UserPatch = JsonPatchFor[User, StandardRegistry]

# 3) Later, if your API needs richer semantics, extend the registry
type AdminUserOps = StandardRegistry | IncrementQuotaOp
AdminUserPatch = JsonPatchFor[User, AdminUserOps]
```

## Why this library exists

[RFC 6902](https://datatracker.ietf.org/doc/html/rfc6902) is deliberately small.
That is good for interoperability, but it leaves a lot unsaid when the patch
document itself becomes part of an API contract.

In practice, many teams either avoid PATCH altogether or reach for JSON Merge
Patch because it feels easier to reason about. That trade-off is understandable.
Generic patch documents are hard to govern across trust boundaries, array
positions are brittle, and mutation intent is often hidden inside low-level
`add` or `replace` steps.

Those problems get sharper when PATCH traffic comes from browsers, internal
services, third-party integrations, and generated clients. A `list[dict]` body
is no longer enough. The route needs to describe its mutation vocabulary
explicitly.

JsonPatchX is built around that gap.

## One adoption path, not two products

You do not have to buy into the whole vision on day one.

1. Use `JsonPatch` when you want plain RFC 6902 patch application.
2. Use `JsonPatchFor[Model, StandardRegistry]` when you want standard RFC
   operations, but as a typed FastAPI/Pydantic contract.
3. Add custom operations, route-level registries, and alternative selectors only
   when your domain actually needs them.

That progression matters. JsonPatchX is not a forked ecosystem where “simple”
and “advanced” are separate products. The standard path is the first path.

## What JsonPatchX adds once you need it

When PATCH becomes a public API surface, JsonPatchX lets you make that surface
explicit:

- patch operations are Pydantic models, so malformed payloads fail before
  mutation
- the patched result can be revalidated against a target model
- OpenAPI is generated from the same operation models used at runtime
- registries let each route accept only the operations it actually supports
- custom operations can express domain intent such as `increment`, `toggle`, or
  `replace_substring`
- alternative pointer backends, including JSONPath-backed ones, can be
  introduced as opt-in targeting strategies

Custom operations do not have to be exotic. Often the win is making familiar
mutations safer and more legible.

## The bigger argument

JsonPatchX is making a larger claim about PATCH API design.

JSON Patch has been minimal for a long time.
[JSONPath](https://datatracker.ietf.org/doc/html/rfc9535) is now standardized.
The ecosystem is in a good place to explore richer PATCH contracts: better
targeting, better semantics, and better governance.

The project is not arguing that every PATCH endpoint should invent its own
language. It is arguing that when an API already has mutation rules, those rules
should live in explicit, typed, testable operation contracts instead of ad hoc
conventions.

Start with the RFC. Keep the extensions opt-in. Let the better designs earn
their place.
