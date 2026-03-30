# Config-Driven Operation Rollout

If different environments or tenants need different PATCH vocabularies, build
registries from config and feature flags.

## Runtime Registry Construction Pattern

```python
from typing import Union

from jsonpatchx import AddOp, RemoveOp, ReplaceOp


AVAILABLE_OPS = {
    "add": AddOp,
    "remove": RemoveOp,
    "replace": ReplaceOp,
    "increment_quota": IncrementQuotaOp,
}


def build_registry(enabled_names: list[str], *, enable_increment: bool) -> object:
    ops: list[type[object]] = [AVAILABLE_OPS[name] for name in enabled_names]

    if enable_increment and "increment_quota" not in enabled_names:
        ops.append(IncrementQuotaOp)

    if not ops:
        raise ValueError("Registry cannot be empty")

    return Union[tuple(ops)]  # type: ignore[misc]
```

```python
RuntimeRegistry = build_registry(
    ["add", "remove", "replace"],
    enable_increment=feature_flags.increment_quota,
)

UserPatch = JsonPatchFor[User, RuntimeRegistry]
```

## Notes

- this is a deployment pattern, not a separate JsonPatchX config loader
- keep config names stable and map them to operation classes explicitly
- snapshot your OpenAPI output per rollout mode when contracts differ

Static type checker caveats for runtime-built unions:
[Recursive Bound Limitation](recursive-bound-limitation.md).
