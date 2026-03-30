# Custom Operations

Custom operations let you treat PATCH as a domain language, not only a transport
diff.

Operations are Pydantic models (`OperationSchema`) with explicit fields and an
`apply()` method.

## What Makes a Good Custom Operation

- clear intent (`increment_quota`, `swap`, `append_unique`)
- explicit pointer/value contracts
- deterministic failure modes
- OpenAPI-friendly schema metadata

## Pointer Methods Available in Operations

- `get(doc)`
  - type-gated pointer resolution against the doc
- `add(doc, value)`
  - type-gated RFC 6902 add
- `remove(doc)`
  - type-gated RFC 6902 remove

## Minimal Pattern

```python
from typing import Literal

from pydantic import Field

from jsonpatchx import JSONPointer, JSONValue, OperationSchema, ReplaceOp
from jsonpatchx.types import JSONNumber


class IncrementByOp(OperationSchema):
    op: Literal["increment_by"] = "increment_by"
    path: JSONPointer[JSONNumber]
    amount: JSONNumber = Field(gt=0)

    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        return ReplaceOp(path=self.path, value=current + self.amount).apply(doc)
```

This composes existing operations while preserving typed pointer contracts.

## Advanced Example: `SwapOp`

```python
from typing import Literal, Self

from pydantic import ConfigDict, model_validator
from typing_extensions import override

from jsonpatchx import (
    AddOp,
    JSONPointer,
    JSONValue,
    OperationSchema,
    OperationValidationError,
)


class SwapOp(OperationSchema):
    model_config = ConfigDict(
        title="Swap operation",
        json_schema_extra={
            "description": (
                "Swaps the values at paths a and b. "
                "Paths a and b may not be proper prefixes of each other."
            )
        },
    )

    op: Literal["swap"] = "swap"
    a: JSONPointer[JSONValue]
    b: JSONPointer[JSONValue]

    @model_validator(mode="after")
    def _reject_proper_prefixes(self) -> Self:
        if self.a.is_parent_of(self.b):
            raise OperationValidationError(
                "pointer 'b' cannot be a child of pointer 'a'"
            )
        if self.b.is_parent_of(self.a):
            raise OperationValidationError(
                "pointer 'a' cannot be a child of pointer 'b'"
            )
        return self

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        value_a = self.a.get(doc)
        value_b = self.b.get(doc)
        doc = AddOp(path=self.a, value=value_b).apply(doc)
        return AddOp(path=self.b, value=value_a).apply(doc)
```

## OpenAPI Snapshot for `SwapOp`

```json
{
  "SwapOp": {
    "additionalProperties": true,
    "description": "Swaps the values at paths a and b. Paths a and b may not be proper prefixes of each other.",
    "properties": {
      "op": {
        "const": "swap",
        "default": "swap",
        "description": "The operation to perform.",
        "title": "Op",
        "type": "string"
      },
      "a": {
        "description": "JSON Pointer (RFC 6901) string",
        "format": "json-pointer",
        "title": "A",
        "type": "string",
        "x-pointer-type-schema": {}
      },
      "b": {
        "description": "JSON Pointer (RFC 6901) string",
        "format": "json-pointer",
        "title": "B",
        "type": "string",
        "x-pointer-type-schema": {}
      }
    },
    "required": ["a", "b", "op"],
    "title": "Swap operation",
    "type": "object"
  },
  "PatchRequestItemsDiscriminator": {
    "$ref": "#/$defs/UserPatchOperation"
  }
}
```

## Register and Use

After defining the operation, add it to a registry and use that registry in
`JsonPatch` (plain JSON) or `JsonPatchFor` (FastAPI contracts).
