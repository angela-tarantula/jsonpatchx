# Agentic Patching

JsonPatchX makes **safe and reliable** agentic JSON patching possible: instead
of asking a coding agent to manipulate JSON directly, you give it a typed Python
toolkit of reviewed patch operation models. If those operations are described
well in an OpenAPI spec, agents can discover the ones they need and write Python
against the corresponding models.

The target might be a local document, a file, or an HTTP request later; the
pattern does not depend on a PATCH endpoint.

## The Core Pattern

Agentic patching has four parts:

- OpenAPI is the discovery surface.
- The Python operation package is the SDK.
- `JsonPatch(...)` is the validator and executor.
- MCP is optional glue if discovery or execution needs to happen remotely.

This matches the direction described by
[Cloudflare's Code Mode](https://blog.cloudflare.com/code-mode-mcp/) and
[Pydantic's argument that agents would rather write code](https://pydantic.dev/articles/your-agent-would-rather-write-code/):
the agent should search a compact semantic catalog, then act through typed code.

## Publish a Patch Toolkit

Agentic patching depends on breadth. The toolkit should be a large reviewed
corpus of narrow, intentful operations an agent can search and compose for
arbitrary JSON mutation tasks.

For example:

```python
# agent_patch_toolkit/__init__.py

from .arrays import AppendUniqueOp, DeduplicateArrayOp, RemoveValueOp
from .assertions import AssertNotEqualOp, AssertRegexMatchOp, RequireMaxOp, RequireMinOp
from .conversion import ParseNumberOp, StringifyOp
from .numbers import ClampOp, IncrementOp, MultiplyOp, RoundOp
from .objects import AddMissingKeyOp, MergeObjectOp, RemoveKeysOp, RenameKeyOp
from .scalars import SetDefaultOp, ToggleOp
from .strings import RegexReplaceOp, ReplaceSubstringOp, StrConcatOp

type AgentPatchToolkit = (
    AddMissingKeyOp
    | AppendUniqueOp
    | AssertNotEqualOp
    | AssertRegexMatchOp
    | ClampOp
    | DeduplicateArrayOp
    | IncrementOp
    | MergeObjectOp
    | MultiplyOp
    | ParseNumberOp
    | RegexReplaceOp
    | RemoveKeysOp
    | RemoveValueOp
    | RenameKeyOp
    | ReplaceSubstringOp
    | RequireMaxOp
    | RequireMinOp
    | RoundOp
    | SetDefaultOp
    | StringifyOp
    | StrConcatOp
    | ToggleOp
    # ... many more reviewed operations
)
```

A corpus like this gives the agent something much better than raw RFC 6902
primitives: it can discover and compose operations whose contracts already
express the mutation it intends.

## Put Discovery Metadata on the Operation Model

Operation names are not enough. An agent trying to cap a value at `100` may
never think to search for `ClampOp`.

Put discovery metadata on the model itself so the Python surface and the schema
surface stay in sync:

```python
from typing import Literal, Self, override

from pydantic import ConfigDict, Field, model_validator
from pydantic.experimental.missing_sentinel import MISSING

from jsonpatchx import JSONPointer, JSONValue, OperationSchema, ReplaceOp
from jsonpatchx.types import JSONNumber


class ClampOp(OperationSchema):
    model_config = ConfigDict(
        title="Clamp operation",
        validate_default=False,
        json_schema_extra={
            "description": (
                "Clamp a numeric value into an inclusive range. "
                "Useful for capping, limiting, bounding, flooring, "
                "or applying a ceiling."
            ),
            "x-discovery-terms": [
                "cap",
                "limit",
                "bound",
                "ceiling",
                "floor",
                "maximum",
                "minimum",
            ],
            "examples": [{"op": "clamp", "path": "/score", "max": 100}],
            "anyOf": [{"required": ["min"]}, {"required": ["max"]}],
        },
    )

    op: Literal["clamp"] = "clamp"
    path: JSONPointer[JSONNumber] = Field(
        description="Pointer to the numeric value to clamp."
    )
    min: JSONNumber = Field(
        default=MISSING,
        description="Inclusive lower bound.",
    )
    max: JSONNumber = Field(
        default=MISSING,
        description="Inclusive upper bound.",
    )

    @model_validator(mode="after")
    def _validate_bounds(self) -> Self:
        has_min = "min" in self.model_fields_set
        has_max = "max" in self.model_fields_set

        if not has_min and not has_max:
            raise ValueError("clamp requires at least one of min or max")
        if has_min and has_max and self.min > self.max:
            raise ValueError("clamp requires min <= max")
        return self

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)

        if "min" in self.model_fields_set:
            current = max(self.min, current)
        if "max" in self.model_fields_set:
            current = min(self.max, current)

        return ReplaceOp(path=self.path, value=current).apply(doc)
```

JsonPatchX does not define one required discovery vocabulary here. The important
part is that the metadata lives on the operation model and ships into OpenAPI
from the same source of truth.

## Execute Through the Python SDK

Once the agent has found the right operations, it should use the Python models
directly:

```python
from jsonpatchx import JsonPatch

from agent_patch_toolkit import (
    AgentPatchToolkit,
    ClampOp,
    IncrementOp,
    MultiplyOp,
)

patch = JsonPatch(
    [
        MultiplyOp(path="/stats/xp", scalar=2),
        IncrementOp(path="/stats/xp", amount=20),
        ClampOp(path="/stats/xp", max=100),
    ],
    registry=AgentPatchToolkit,
)

document = patch.apply(document)
```

The agent did not have to assemble JSON text by hand. It also did not have to
translate intent into brittle RFC 6902 sequences or raw JSON structure.

It wrote Python, instantiated typed operations, and let `JsonPatch(...)`
validate the patch before execution. If the patch later needs to cross a process
boundary, it is still ordinary JSON Patch on the wire.

## Use Validation and Patch Errors for Course Correction

This pattern gives the agent a better retry loop than "emit JSON and hope":

- invalid operation inputs fail during model construction or `JsonPatch(...)`
  validation
- operation-level validation can raise structured `PydanticCustomError`
- runtime document-state failures raise `PatchConflictError`

## Iterate on the Toolkit

Agentic patching gets better over time. The corpus should evolve from two kinds
of evidence: operations the agent wanted but could not find, and operations it
found but used badly or ambiguously.

### Log Missing Operations

Whenever the agent wants to do something but cannot find a good operation for
it, that gap should be logged somewhere durable.

At minimum, log:

- the task the agent was trying to complete
- the search terms or operations it considered
- the missing mutation or guard it wanted to express
- a small example input and desired output

Over time, that backlog becomes the roadmap for new reviewed operation models
that get added to the corpus.

### Measure Misused Operations

It is also worth capturing metrics around misused operations. Repeated
validation failures, conflict-heavy retries, or frequent human corrections are
signals that an existing operation's name, examples, description, or discovery
metadata needs work.

Those signals help improve the operations you already have, not just identify
the ones that are missing.

### Draft New Operations Carefully

Some teams may also choose to let agents draft missing operation models on the
fly. That can work well, but draft operations should usually stay separate from
the reviewed published toolkit until a human decides they are generic enough,
safe enough, and well documented enough to keep.

## Publishing Guidance

- Publish the toolkit as a stable Python import surface.
- Publish matching OpenAPI from the same operation models.
- Put discovery terms, descriptions, and examples on the operation model itself.
- Do not rely on operation names alone for discovery.
- Keep the toolkit reviewed. Agents can draft new operations, but published
  operations should usually go through human review.

The result is a patching workflow in which agents search a schema-rich catalog,
write Python against a controlled toolkit, validate early, and recover from
clear patch failures when they need to try again.
