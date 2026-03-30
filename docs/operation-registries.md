# Operation Registries

Registries are the governance boundary for PATCH behavior.

A registry is a union of operation models. Only operations in that union can be
parsed and applied.

## Why Registries Exist

Registries let you control mutation surface area explicitly:

- expose fewer verbs on public routes
- allow richer verbs on internal routes
- roll out operations behind flags or config

## Standard RFC Registry

```python
from jsonpatchx import StandardRegistry
```

Equivalent explicit union:

```python
from jsonpatchx import AddOp, CopyOp, MoveOp, RemoveOp, ReplaceOp, TestOp

type StandardRegistry = AddOp | CopyOp | MoveOp | RemoveOp | ReplaceOp | TestOp
```

## Compose Registries

```python
from jsonpatchx import StandardRegistry

type DevRegistry = StandardRegistry | IncrementOp | SwapOp
```

## Route-Level Allow-Listing

```python
from jsonpatchx import AddOp, RemoveOp, ReplaceOp, StandardRegistry

type PublicRegistry = AddOp | RemoveOp | ReplaceOp
type InternalRegistry = StandardRegistry
```

## Runtime Registries

```python
from typing import Union

ops = [AddOp, RemoveOp, ReplaceOp]
if feature_enabled("swap"):
    ops.append(SwapOp)

RuntimeRegistry = Union[tuple(ops)]  # type: ignore[misc]
```

Runtime type construction caveats:
[Recursive Bound Limitation](recursive-bound-limitation.md).

## Failure Mode

If an operation is missing from the active registry, parsing fails before
apply-time. That is the intended contract boundary.
