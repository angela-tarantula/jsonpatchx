# Registries and Routes

A registry is the set of operations a route will accept. If an operation is not
in the registry, the request fails during validation before any mutation runs.

Registries are a practical way to apply
[least privilege](https://en.wikipedia.org/wiki/Principle_of_least_privilege) to
mutation surfaces.

Good patterns include:

- a narrow public registry
- a broader internal registry
- a dev-only registry for experiments
- a superuser route with elevated auth and a wider registry

## Why Route-Specific Registries Matter

This is about route-level control. You don’t need custom operations for this to
matter.

- **Security boundaries** - Some operations are safe internally but risky to
  expose. For example,
  [test](https://datatracker.ietf.org/doc/html/rfc6902#section-4.6) can be
  abused to probe for values a client should not be able to observe.
- **Different audiences** - Public, partner, internal, and admin routes often
  need different mutation vocabularies, even over the same resource.
- **Safer evolution** - New or experimental operations can be introduced in
  internal routes first without committing them to public APIs.

## Create Registries

It's as simple as this:

```python
from jsonpatchx import AddOp, RemoveOp, ReplaceOp, MoveOp, CopyOp, TestOp

type WriteOnlyRegistry = AddOp | RemoveOp | ReplaceOp | MoveOp | CopyOp
type StandardRegistry = WriteOnlyRegistry | TestOp
```

Both `JsonPatch` and `JsonPatchFor` use `StandardRegistry` (the six standard RFC
6902 operations) by default.

But you can use your own:

```python
JsonPatch(ops, registry=WriteOnlyRegistry).apply(doc)
```

```python
@app.patch("/users/{user_id}", response_model=User)
def patch_user(user_id: int, patch: JsonPatchFor[User, WriteOnlyRegistry]) -> User:
    ...
```

## Environment-Specific Registries

You can load operations from a startup-time configuration source and build a
registry using `Union[*ops]`:

```python
from typing import Union

registry_ops = [operation_by_name[name] for name in load_config("registry.json")]
type MyRegistry = Union[*registry_ops]
```

> Type checkers will complain about runtime-generated types like this because
> they can't reason about them. You can safely use `# type: ignore` here.

You can also vary registries based on environment or deployment context:

```python
import os
from typing import Union
from jsonpatchx import StandardRegistry

extras = [operation_by_name[name] for name in names if os.getenv(name)]
type MyRegistry = Union[StandardRegistry, *extras]
```

This allows you to enable or disable specific API capabilities via environment
flags or config files without modifying your route logic.
