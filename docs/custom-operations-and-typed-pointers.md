# Custom Operations and Typed Pointers

This is the first extension layer beyond baseline RFC operations.

In JsonPatchX, every operation is defined as a subclass of `OperationSchema`.
Because these are Pydantic models, each operation bundles together:

- Input validation
- Runtime behavior
- OpenAPI schema generation

This makes operations easy to reason about, test, and extend.

## Defining a Custom Operation

```python
from typing import Literal

from pydantic import Field

from jsonpatchx import JSONPointer, JSONValue, OperationSchema, ReplaceOp
from jsonpatchx.types import JSONNumber


class IncrementOp(OperationSchema):
    op: Literal["increment"]
    path: JSONPointer[JSONNumber]
    amount: JSONNumber = Field(gt=0)

    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        return ReplaceOp(path=self.path, value=current + self.amount).apply(doc)
```

Breakdown:

1. `op` is the discriminator used for parsing and schema generation.
2. `path: JSONPointer[JSONNumber]` is a typed path contract. You provide it as a
   standard JSON Pointer string (e.g. "/counter"), which is parsed into a
   `JSONPointer` during validation.
3. `amount: JSONNumber = Field(gt=0)` adds both JSON-type constraints and domain
   validation.
4. `apply()` defines mutation semantics: read the current value, compute the
   next value, then delegate write behavior to `ReplaceOp`.

## JSON-Native Helper Types

JsonPatchX provides helper types that model JSON semantics directly:

- `JSONString`, `JSONNumber`, `JSONBoolean`, and `JSONNull` for JSON primitive
  values
- `JSONArray[T]` and `JSONObject[T]` for typed JSON containers
- `JSONValue` for any valid JSON value

`JSONNumber` represents finite numeric values (`int | float`) and intentionally
excludes `bool`.

## `JSONPointer[T]` Semantics

On its own, `JSONPointer[T]` is a typed path descriptor. It does not assert that
a given document currently contains that path; existence and type are enforced
only when pointer operations run.

- `get(doc)` resolves the path and validates the resolved target against `T`.
- `add(doc, value)` validates `value` against `T` before writing.
- `remove(doc)` is type-gated: it validates the current target against `T`
  before deleting.

In the `IncrementOp` example, `current = self.path.get(doc)` runs before any
write step. If the path is missing or the resolved target is not numeric, the
operation fails before mutation.
