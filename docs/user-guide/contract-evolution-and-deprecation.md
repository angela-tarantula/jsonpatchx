# Contract Evolution and Deprecation

Operation schemas are API surface.

Once clients send them over the wire, changing them is not just a refactor. It
is a contract change.

That does not mean PATCH has to be rigid. It means the evolution needs to be
deliberate.

## The safest rule

Keep an existing `op` stable unless you are prepared to support its current
meaning for older clients.

That simple rule gets you most of the way there.

In practice:

- additive changes are the safest changes
- new fields should default to existing behavior
- a real semantic break deserves a new `op`
- deprecation should happen before removal
- registries are the right place to control where old and new contracts coexist

## A concrete example

Here is a small operation that replaces a substring at a string path:

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

**Additive change.** Suppose clients now need a non-strict mode. Keep the same
`op` and add a field that preserves the old behavior by default.

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

Existing clients keep working because `strict=True` preserves the original
behavior.

**Deprecation.** Now imagine you decide non-strict mode was a mistake. Do not
remove the field the same day you stop liking it. Mark it deprecated first.

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

That gives OpenAPI and client developers a transition period instead of a
surprise.

**Breaking semantic change.** If you are changing the meaning of the operation
itself, do not mutate the old one in place. Create a new `op`.

For example:

- keep `replace_substring`
- introduce `replace_substring_v2`
- let both exist for a while through registry policy
- remove the older one on a real schedule

That is easier for clients to reason about than an operation whose name stays
the same while its semantics quietly drift.

## Let registries carry the rollout

Registries are how you make evolution manageable in practice.

They let you do things like:

- expose both old and new operations internally before a public rollout
- keep a deprecated operation on one route while removing it from another
- test migration behavior with a dev-only contract profile
- version the accepted operation set without changing the transport format

That is one of the strongest arguments for treating PATCH as a contract surface
instead of just a list of mutation dicts.
