# Type System Notes

JsonPatchX models JSON semantics directly, not Python's broader runtime
coercions.

## Strict JSON Helpers

Use helper types to reason in JSON terms:

- `JSONNumber`: `int | float`, explicitly excluding `bool`
- `JSONString`, `JSONBoolean`, `JSONNull`
- `JSONArray[T]`, `JSONObject[T]`
- `JSONValue`: recursive JSON union

Non-finite numbers (`NaN`, `Infinity`, `-Infinity`) are rejected.

## Why This Matters

Pydantic model fields describe data shape. JsonPatchX operation schemas describe
mutation intent.

That separation is important for governed PATCH APIs:

- your model may allow a broad type
- your operation can still intentionally narrow what a specific patch verb is
  allowed to target

## Example: Intent Narrowing

```python
from typing import Literal

from jsonpatchx import JSONPointer, JSONValue, OperationSchema, ReplaceOp
from jsonpatchx.types import JSONNumber


class IncrementOp(OperationSchema):
    op: Literal["increment"] = "increment"
    path: JSONPointer[JSONNumber]
    value: JSONNumber

    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        return ReplaceOp(path=self.path, value=current + self.value).apply(doc)
```

`path` is explicitly numeric. If the resolved target is non-numeric, apply fails
before mutation.
