# JSONPath Selection

Use this section when pointer-level targeting is not expressive enough for your
domain.

## Current Scope

JsonPatchX operations are built around single-target pointer semantics.

You can still bind alternate pointer syntaxes through custom pointer backends,
including backends from `python-jsonpath`.

```python
from jsonpath import JSONPointer as JsonPathPointer

from jsonpatchx import JSONPointer, JSONValue


class URIJsonPathPointer(JsonPathPointer):
    def __init__(self, pointer: str) -> None:
        super().__init__(pointer, uri_decode=True, unicode_escape=False)


path: JSONPointer[JSONValue, URIJsonPathPointer]
```

## Selector-Style Behavior

If you need multi-match selector behavior, keep it inside a custom operation and
make fan-out behavior deterministic (ordering, conflict handling, and failure
mode).

For backend protocol constraints and guarantees, see
[Pointer Backends](pointer-backends.md).

## Continue

Next: [Config-Driven Operation Rollout](config-driven-operation-rollout.md)
