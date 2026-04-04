# Custom Operations

Custom operations are where JsonPatchX moves from “typed JSON Patch” to “PATCH
contracts that fit a real domain.”

This does not mean inventing a new language for every API. It means promoting
recurring mutation intent into a first-class operation model when the generic
RFC operations stop being expressive enough.

If your route keeps receiving “read the current number, add 1, write it back” as
a fragile `replace`, that is a good candidate for a custom op.

## A concrete example: `increment`

```python
from typing import Literal

from pydantic import Field

from jsonpatchx import JSONPointer, JSONValue, OperationSchema, ReplaceOp
from jsonpatchx.types import JSONNumber


class IncrementQuotaOp(OperationSchema):
    op: Literal["increment_quota"] = "increment_quota"
    path: JSONPointer[JSONNumber]
    amount: JSONNumber = Field(gt=0)

    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        return ReplaceOp(path=self.path, value=current + self.amount).apply(doc)
```

This is a good example of how JsonPatchX wants extensions to work.

The operation model carries its own parse-time contract:

- `op` is the discriminator used in the registry union
- `path` is not just a string; it is a `JSONPointer` that expects a numeric
  target
- `amount` is validated before any mutation runs

The runtime behavior is then simple and explicit: read the current value,
compute the next value, reuse `ReplaceOp` to perform the write.

## Typed pointers are where extension becomes safe

The most important line above is not `amount`. It is this one:

```python
path: JSONPointer[JSONNumber]
```

`JSONPointer[T]` is a contract about the shape of the value the pointer is
expected to resolve.

That contract is enforced when the pointer is used:

- `get(doc)` validates the resolved target against `T`
- `add(doc, value)` validates the value before writing
- `remove(doc)` validates the existing target before deleting it

That means your custom operation can fail early and clearly when a path exists
but points at the wrong kind of data.

## Custom can mean safer, not just novel

A custom operation does not have to represent a brand-new mutation category.
Sometimes the point is to wrap a familiar mutation in better semantics.

```python
from typing import Literal

from jsonpatchx import (
    JSONPointer,
    JSONValue,
    OperationSchema,
    PatchConflictError,
    ReplaceOp,
)
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

This is still “just a replace” in one sense. The difference is that the payload
now expresses intent directly, and the failure mode is specific to that intent.

## JSON helper types are worth using

JsonPatchX includes strict JSON helper types for exactly this kind of operation
design:

- `JSONBoolean`
- `JSONNumber`
- `JSONString`
- `JSONNull`
- `JSONArray[T]`
- `JSONObject[T]`
- `JSONValue`

They model JSON semantics directly, which keeps contracts honest. For example,
`JSONNumber` is numeric JSON data, not Python’s broader idea of “anything
number-like.”

## Good custom operations have a small shape

A custom operation is usually worth keeping when it does five things well:

- names a real domain action
- keeps its payload small and explicit
- validates the important invariants before mutation
- has clear conflict behavior
- composes with the rest of the registry cleanly

A custom operation is usually not worth keeping when it is only a thin wrapper
around an arbitrary script.

The goal is not novelty. The goal is a mutation vocabulary that reads like your
API.
