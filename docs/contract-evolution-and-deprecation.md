# Contract Evolution and Deprecation

Treat operation contracts as versioned API surface.

## Preferred Evolution Strategy

1. add behavior with new fields or new operations
2. keep old behavior available through an overlap window
3. deprecate obsolete fields or operations explicitly
4. remove deprecated paths on a scheduled boundary

## Example: Additive Operation Versioning

```python
from typing import Literal

from jsonpatchx import JSONPointer, JSONValue, OperationSchema, ReplaceOp
from jsonpatchx.types import JSONNumber


class IncrementQuotaV1(OperationSchema):
    op: Literal["increment_quota"] = "increment_quota"
    path: JSONPointer[JSONNumber]
    amount: JSONNumber

    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        return ReplaceOp(path=self.path, value=current + self.amount).apply(doc)


class IncrementQuotaV2(OperationSchema):
    op: Literal["increment_quota_v2"] = "increment_quota_v2"
    path: JSONPointer[JSONNumber]
    delta: JSONNumber

    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        return ReplaceOp(path=self.path, value=current + self.delta).apply(doc)
```

```python
type RegistryV1 = StandardRegistry | IncrementQuotaV1
type RegistryV2 = StandardRegistry | IncrementQuotaV1 | IncrementQuotaV2
```

## Example: Field Deprecation

```python
from pydantic import Field


class SetQuotaOp(OperationSchema):
    op: Literal["set_quota"] = "set_quota"
    path: JSONPointer[JSONNumber]
    value: JSONNumber
    reason: str | None = Field(default=None, deprecated=True)
```

Use endpoint-level registries to control which versions are accepted in each
environment.

## Continue

Next:
[Error Semantics and Contract Tests](error-semantics-and-contract-tests.md)
