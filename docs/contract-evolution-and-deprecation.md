# Evolving Contracts

Operation schemas are API surface.

That means changing an operation is not “just changing an internal model.” It is
changing a request contract that clients send over the wire.

JsonPatchX makes that surface explicit. The trade-off is that you should version
and deprecate it with the same care you would apply to any other request model.

## Safe ways to change an operation

The safest rule is simple:

Keep an existing `op` stable unless you are willing to own its current meaning
for old clients.

That leads to a practical set of rules.

1. Prefer additive changes.
2. New fields should default to existing behavior.
3. Use a new `op` literal for a real semantic break.
4. Deprecate before removing.
5. Roll schema changes out with registry and deployment policy, not only code
   merges.

## Change guide

| Change                    | What to do                                             |
| ------------------------- | ------------------------------------------------------ |
| Add optional behavior     | Add a new field with a safe default                    |
| Relax or tighten a mode   | Add a field that makes the mode explicit               |
| Rename a field            | Add the new field, deprecate the old one, remove later |
| Change core semantics     | Introduce a new `op`                                   |
| Remove an optional branch | Deprecate it first, then remove on a schedule          |

## Example: evolving `replace_substring`

### Initial version

```python
from typing import Literal

from jsonpatchx import JSONPointer, JSONValue, OperationSchema, PatchConflictError, ReplaceOp
from jsonpatchx.types import JSONString


class ReplaceSubstringOp(OperationSchema):
    op: Literal["replace_substring"] = "replace_substring"
    path: JSONPointer[JSONString]
    old: JSONString
    new: JSONString

    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        if self.old not in current:
            raise PatchConflictError(f"{self.old!r} is not in {current!r}")

        return ReplaceOp(
            path=self.path,
            value=current.replace(self.old, self.new),
        ).apply(doc)
```

### Additive evolution

Suppose clients now need a non-strict mode.

That is an additive change, so keep the `op` and add a field with the old
behavior as the default.

```python
from pydantic import Field
from jsonpatchx.types import JSONBoolean


class ReplaceSubstringOp(OperationSchema):
    op: Literal["replace_substring"] = "replace_substring"
    path: JSONPointer[JSONString]
    old: JSONString
    new: JSONString
    strict: JSONBoolean = Field(default=True)

    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)

        if self.strict and self.old not in current:
            raise PatchConflictError(
                f"strict mode is enabled and {self.old!r} is not in {current!r}"
            )

        return ReplaceOp(
            path=self.path,
            value=current.replace(self.old, self.new),
        ).apply(doc)
```

Existing clients keep working because `strict=True` preserves old behavior.

### Deprecation

Now suppose you decide non-strict mode was a mistake.

Deprecate the field before removing it.

```python
from pydantic import Field


class ReplaceSubstringOp(OperationSchema):
    op: Literal["replace_substring"] = "replace_substring"
    path: JSONPointer[JSONString]
    old: JSONString
    new: JSONString
    strict: JSONBoolean = Field(
        default=True,
        deprecated=True,
        description=(
            "Deprecated. Non-strict mode will be removed. "
            "This operation will always behave as strict=True."
        ),
    )

    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)

        if self.strict and self.old not in current:
            raise PatchConflictError(
                f"strict mode is enabled and {self.old!r} is not in {current!r}"
            )

        return ReplaceOp(
            path=self.path,
            value=current.replace(self.old, self.new),
        ).apply(doc)
```

The point of deprecation is not ceremony. It is to give clients and your own
documentation a stable transition period.

### Breaking semantic change

If you were changing the meaning of the operation itself, do not mutate
`replace_substring` in place.

Create a new `op`, such as `replace_substring_v2`, and let both contracts
coexist for a while under registry policy.

## Coordinate evolution with rollout

Schema evolution works best when it is paired with runtime policy:

- registries control which operations are accepted where
- feature flags control when a new contract appears
- OpenAPI snapshots tell you exactly what changed

That is how you keep PATCH contracts predictable. The schema changes, the route
policy changes, and the docs change together.
