# Evolving PATCH Contracts

Operation schemas are API surface. Changes to them should preserve compatibility
on purpose.

## Compatibility Rules

The safest rules are simple:

- additive changes are the safest changes
- new fields should preserve existing behavior by default
- a semantic break deserves a new `op`
- deprecation should happen before removal
- registries are where old and new contracts can coexist deliberately

## Contract Evolution by Example

A mutation like "replace substring" is hard to get right the first time.

### Baseline Contract of `ReplaceSubstringOp`

```python
from typing import Literal
from pydantic import Field
from jsonpatchx import JSONPointer, JSONValue, OperationSchema, ReplaceOp, PatchConflictError
from jsonpatchx.types import JSONString, JSONBoolean

class ReplaceSubstringOp(OperationSchema):
    op: Literal["replace_substring"] = "replace_substring"
    path: JSONPointer[JSONString]
    old: JSONString
    new: JSONString

    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        if self.old not in current:
            raise PatchConflictError(f"{self.old!r} is not in {current!r}")

        replaced = current.replace(self.old, self.new)
        return ReplaceOp(path=self.path, value=replaced).apply(doc)
```

### Additive Change

If clients now need a non-strict mode, keep the same `op` and add a field that
preserves the old behavior by default.

```python
from typing import Literal
from pydantic import Field
from jsonpatchx import JSONPointer, JSONValue, OperationSchema, ReplaceOp, PatchConflictError
from jsonpatchx.types import JSONString, JSONBoolean

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

        replaced = current.replace(self.old, self.new)
        return ReplaceOp(path=self.path, value=replaced).apply(doc)
```

Because `strict=True` preserves the original behavior, existing clients keep
working.

### Deprecation

If that field later needs to go away, deprecate it before removing it. That
gives OpenAPI and client developers a transition period instead of a surprise.

```python
from typing import Literal
from pydantic import Field
from jsonpatchx import JSONPointer, JSONValue, OperationSchema, ReplaceOp, PatchConflictError
from jsonpatchx.types import JSONString, JSONBoolean

class ReplaceSubstringOp(OperationSchema):
    op: Literal["replace_substring"] = "replace_substring"
    path: JSONPointer[JSONString]
    old: JSONString
    new: JSONString
    strict: JSONBoolean = Field(default=True, deprecated=True)

    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)

        if self.old not in current:
            if "strict" not in self.model_fields_set or self.strict:
                raise PatchConflictError(
                    f"strict mode is enabled and {self.old!r} is not in {current!r}"
                )

        replaced = current.replace(self.old, self.new)
        return ReplaceOp(path=self.path, value=replaced).apply(doc)
```

Pydantic's
[`model_fields_set`](https://docs.pydantic.dev/latest/api/base_model/#pydantic.BaseModel.model_fields_set)
distinguishes omission from explicit use, so
[DeprecationWarning](https://docs.python.org/3/library/warnings.html#warning-categories)
becomes a signal that clients are still sending the deprecated field.

### Contract Tightening

Python's
[`str.replace()`](https://docs.python.org/3/library/stdtypes.html#str.replace)
is broad. `str.replace(old, new, /, count=-1)` replaces all occurrences by
default, limits replacements when `count` is given, and even allows `old=""`.

A PATCH contract does not need to expose every lever. If you decide this
operation should only replace a non-empty substring, tighten the field contract:

```python
from typing import Literal
from pydantic import Field
from jsonpatchx import JSONPointer, JSONValue, OperationSchema, ReplaceOp, PatchConflictError
from jsonpatchx.types import JSONString, JSONBoolean

class ReplaceSubstringOp(OperationSchema):
    op: Literal["replace_substring"] = "replace_substring"
    path: JSONPointer[JSONString]
    old: JSONString = Field(min_length=1)
    new: JSONString

    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        if self.old not in current:
            raise PatchConflictError(f"{self.old!r} is not in {current!r}")

        replaced = current.replace(self.old, self.new)
        return ReplaceOp(path=self.path, value=replaced).apply(doc)
```

If you use [semantic versioning](https://semver.org/), this is a breaking
change.

### Breaking Semantic Change

If the meaning of the operation itself changes, do not mutate the old one in
place.

For example, if `replace_substring` originally meant "replace all occurrences",
and you now want an operation that replaces only the first occurrence, that is
not the same operation. If you intend to retire the old behavior, deprecate
`replace_substring`, introduce `replace_first_substring`, allow both through
registry policy for a while, then remove the deprecated one.

```python
from pydantic import ConfigDict

class ReplaceSubstringOp(OperationSchema):
    model_config = ConfigDict(json_schema_extra={"deprecated": True})
    ...
```

Changing semantics in place is harder for clients to reason about than adding a
new `op`. For the route-level side of that rollout, see
[Registries and Routes](registries-and-routes.md).
