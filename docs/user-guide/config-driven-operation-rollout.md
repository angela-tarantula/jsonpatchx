# Rolling Out PATCH Contracts

Different environments, tenants, and client cohorts rarely need the same
mutation vocabulary on day one.

That is especially true once you introduce custom operations.

Registries can be built from configuration, feature flags, or named rollout
profiles so you can expose richer PATCH contracts gradually instead of all at
once.

## Build the registry at startup

```python
from typing import Literal, Union

from jsonpatchx import AddOp, JsonPatchFor, RemoveOp, ReplaceOp


AVAILABLE_OPS = {
    "add": AddOp,
    "remove": RemoveOp,
    "replace": ReplaceOp,
    "increment_quota": IncrementQuotaOp,
    "replace_substring": ReplaceSubstringOp,
}


def build_registry(enabled_names: list[str]) -> object:
    ops: list[type[object]] = [AVAILABLE_OPS[name] for name in enabled_names]

    if not ops:
        raise ValueError("Registry cannot be empty")

    return Union[tuple(ops)]  # type: ignore[misc]


enabled_ops = settings.patch_profiles["billing-admin"]
RuntimeRegistry = build_registry(enabled_ops)

BillingPatch = JsonPatchFor[Literal["BillingAccount"], RuntimeRegistry]
```

This is a deployment pattern, not a separate JsonPatchX configuration language.
That is a good thing. It keeps the mapping between external configuration and
internal operation classes visible in your own codebase.

## Prefer named profiles over ad hoc mutation sets

The safest way to do this is to choose a named contract profile at application
startup and bind the route once.

Good examples:

- `public`
- `internal`
- `beta`
- `tenant_enterprise`
- `billing_admin`

Bad example:

- let each request negotiate its own operation set dynamically

A PATCH contract should be something you can document, test, and support. Named
profiles make that possible.

## Rules that keep this sane

Keep the external names stable and boring. Configuration should refer to
operation names you are prepared to support, not temporary Python implementation
details.

Snapshot OpenAPI per profile when contracts differ. If `public` and `internal`
accept different registries, they should not silently share one schema snapshot.

Separate auth from registry construction. Feature flags and configuration decide
what the route can support. Authentication decides who can reach the route.

Log the active rollout profile. When a PATCH request fails in production, “which
registry was active?” is one of the first questions support and platform teams
ask.

## A note on typing

Runtime-built unions are useful at startup boundaries, but static type checkers
cannot reason about them as well as named type aliases.

That is fine.

Use runtime construction when rollout flexibility matters. Use named aliases
when you want the clearest developer-facing contract in source code.
