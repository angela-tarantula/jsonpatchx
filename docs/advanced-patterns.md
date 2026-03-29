# Advanced Patterns

## Built-In RFC Generic Parameters

Built-in operations are generic, so you can make operation intent explicit:

```python
from jsonpatchx import ReplaceOp
from jsonpatchx.types import JSONNumber

op = ReplaceOp[JSONNumber](path="/quota", value=10)
```

Useful when you want strict pointer-target typing to propagate through composed
operation behavior.

## `JsonPatchRoute` for Assisted FastAPI Wiring

`JsonPatchRoute` is optional helper wiring from `jsonpatchx.fastapi`:

- strict `application/json-patch+json` handling
- request examples
- route kwargs and body wiring helpers
- aligned patch error response mapping

```python
from jsonpatchx.fastapi import JsonPatchRoute

user_patch = JsonPatchRoute(
    UserPatch,
    strict_content_type=True,
    examples={"rename": {"summary": "Rename user", "value": [...]}},
)
```

Use this when you want stronger conventions and less manual FastAPI plumbing.
