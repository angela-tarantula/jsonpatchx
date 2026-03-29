# Operation Registries

Registries are the operational allow-list for JsonPatchX. A registry is a union
of operation models, and only operations in that union are accepted.

## Standard RFC Registry

The built-in RFC registry is:

```python
from jsonpatchx import AddOp, CopyOp, MoveOp, RemoveOp, ReplaceOp, TestOp

type StandardRegistry = AddOp | CopyOp | MoveOp | RemoveOp | ReplaceOp | TestOp
```

## Compose Larger Registries

```python
from jsonpatchx import StandardRegistry  # importable for convenience

type DevRegistry = StandardRegistry | ReplaceSubstringOp | ConcatenateOp | AppendOp
```

## Allow-list Operations Per Route

```python
from jsonpatchx import AddOp, RemoveOp, ReplaceOp, StandardRegistry

type ClientARegistry = AddOp | RemoveOp | ReplaceOp
type ClientBRegistry = StandardRegistry
```

## Runtime Registries from Config/Flags

You can build operation sets dynamically (feature flags, config files, env):

```python
from typing import Union
from your_business_logic import load_ops

dynamic_ops = [AddOp, RemoveOp, ReplaceOp] + load_ops("custom_ops.yml")
RuntimeRegistry = Union[dynamic_ops]  # type: ignore[misc]
```

Use this when operational policy is environment-driven. For static typing
trade-offs of runtime unions, see
[Recursive Bound Limitation](recursive-bound-limitation.md).

## Failure Behavior

If an op is not in the active registry, patch parsing fails before apply-time.
This is how route-level allow-list governance is enforced.
