# Agentic Patching

Agents usually do better when they can search a schema-rich API surface and then
write typed code against it.

That is the same general direction described by
[Cloudflare's Code Mode](https://blog.cloudflare.com/code-mode-mcp/) and
[Pydantic's recent writing on agents writing code](https://pydantic.dev/articles/your-agent-would-rather-write-code):
discovery should be compact and semantic, while execution should happen through
code, types, and validation.

JsonPatchX fits that pattern well.

## What Agents Need

For PATCH specifically, agents usually need four things:

- a discovery surface they can search semantically
- an execution surface they can use from Python
- client-side validation before send
- stable, structured patch failures after send

That means discovery and execution should not be treated as the same problem.

## Make the Operation Model the Source of Truth

In JsonPatchX, an operation model can drive both:

- the Python API an agent imports and instantiates
- the OpenAPI schema an agent or tool indices for discovery

That is the key design move.

Do not make the agent guess from class names alone. Put semantic metadata on the
operation model itself so Python and OpenAPI stay in sync.

```python
from typing import Literal, override

from pydantic import ConfigDict, Field

from jsonpatchx import JSONPointer, JSONValue, OperationSchema, ReplaceOp
from jsonpatchx.types import JSONNumber


class ClampOp(OperationSchema):
    model_config = ConfigDict(
        title="Clamp operation",
        json_schema_extra={
            "description": (
                "Clamp a numeric value into an inclusive range. "
                "Useful for capping, bounding, limiting, flooring, "
                "or applying a ceiling."
            ),
            "x-tags": ["cap", "limit", "bound", "ceiling", "floor", "max", "min"],
            "examples": [{"op": "clamp", "path": "/score", "max": 100}],
        },
    )

    op: Literal["clamp"] = "clamp"
    path: JSONPointer[JSONNumber] = Field(
        description="Pointer to the numeric value to clamp."
    )
    min: JSONNumber | None = Field(default=None, description="Inclusive lower bound.")
    max: JSONNumber | None = Field(default=None, description="Inclusive upper bound.")

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        if self.min is not None:
            current = max(self.min, current)
        if self.max is not None:
            current = min(self.max, current)
        return ReplaceOp(path=self.path, value=current).apply(doc)
```

An agent trying to "cap a value at 100" may never think to search for `ClampOp`.
But it can discover this operation through the description, examples, and
semantic tags published into OpenAPI from the same model.

JsonPatchX does not require one special metadata format here. The important part
is that the metadata lives on the operation model and is published with it.
`json_schema_extra` is the right place to do that.

## OpenAPI for Discovery, Python for Execution

Once the operation models carry semantic metadata, the split becomes simple:

- OpenAPI is the discovery surface.
- Importable Python operations are the execution surface.

For example, an API service can publish a small patch SDK:

```python
# some_service/patching.py

from .ops import ClampOp, IncrementOp, MultiplyOp

type WidgetPatchRegistry = MultiplyOp | IncrementOp | ClampOp
```

An agent or agent-adjacent tool can search the generated OpenAPI for tags,
descriptions, and examples such as "cap", "limit", or "bound", discover
`ClampOp`, then use the Python model directly:

```python
from some_service.patching import ClampOp, WidgetPatchRegistry

from jsonpatchx import JsonPatch

patch = JsonPatch(
    [
        ClampOp(path="/foo/bar", max=100),
    ],
    registry=WidgetPatchRegistry,
)
```

This is the core pattern:

1. Discover the right operation from OpenAPI metadata.
2. Import the Python model for that operation.
3. Build the patch in Python.
4. Validate client-side with `JsonPatch(...)`.
5. Send ordinary JSON Patch on the wire.

## What "SDK" Means Here

In this context, an SDK does not need to be a large generated client.

Usually it is enough to publish:

- the operation models
- the shared registry alias
- optional helper functions or client wrappers

The important part is that agents get a stable Python import surface for
execution.

## Recommendations

- Publish custom operations as importable Python models.
- Export a shared registry alias that matches the PATCH contract.
- Put descriptions, examples, and semantic discovery metadata on the operation
  model itself.
- Treat OpenAPI as the discovery surface, not the execution surface.
- Treat the Python models as the execution surface, not just documentation.
- Keep PATCH failures stable and structured. For that side of the contract, see
  [Error Semantics and Contract Tests](error-semantics-and-contract-tests.md).
- Prefer reviewed operations. Agents can draft new operations in Python, but new
  published operations should usually go through human review.

This gives agents what they want: searchable semantics, typed Python models,
client-side validation, and patch documents that are written as code instead of
assembled as brittle JSON.
