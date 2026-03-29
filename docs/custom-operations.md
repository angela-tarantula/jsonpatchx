# Custom Operations

Custom operations are the main reason to use JsonPatchX over a plain RFC 6902
implementation.

## Minimal Custom Op

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

## Register It

```python
from jsonpatchx import JsonPatch, StandardRegistry

type Registry = StandardRegistry | IncrementByOp

patch = JsonPatch(
    [{"op": "increment_by", "path": "/quota", "amount": 10}],
    registry=Registry,
)

updated = patch.apply({"quota": 100})
```

## Required Rules

- Subclass `OperationSchema`
- Define `op` as a `Literal[...]` field
- Implement `apply(self, doc) -> JSONValue`
- Include the op class in the registry used to parse/apply patches

## Design Tips

- Keep operations narrowly scoped (one clear intent per op)
- Use typed pointers (`JSONPointer[T]`) to enforce path value expectations
- Raise patch-domain errors (`PatchConflictError`, `TestOpFailed`, etc.) for
  expected business failures

## Where to Learn More

- Real custom-op sets: `/examples/recipes.py` and `/examples/recipes2.py`
- FastAPI usage with custom registries: [Demos](demos.md)
