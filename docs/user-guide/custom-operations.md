# Custom Operations

Custom operations are worth adding when low-level operations stop reading like
what the caller actually means.

That does not mean inventing a new mutation language for every API. Usually the
win is much simpler than that. A good custom operation takes a mutation your
clients already keep expressing awkwardly, gives it a clear name, validates the
right things up front, and makes the contract easier to document.

Start small.

## Operation Anatomy

JsonPatchX patch operations are Pydantic-backed models. This section covers the
base class, typed targeting, and JSON-native value types.

### The `OperationSchema` Base Class

All operations, standard and custom, inherit from `OperationSchema`.

Before looking at a custom operation, it helps to see how little machinery is
involved. For example, `ReplaceOp` is conceptually this kind of shape:

```python
from typing import Literal
from jsonpatchx import JSONPointer, JSONValue, OperationSchema, AddOp, RemoveOp

class ReplaceOp(OperationSchema):
    op: Literal["replace"]
    path: JSONPointer[JSONValue]
    value: JSONValue

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        doc = RemoveOp(path=self.path).apply(doc)
        return AddOp(path=self.path, value=self.value).apply(doc)
```

The real implementation may have more detail, but the important thing is the
shape:

- an operation is a Pydantic-backed model

- `op` is the discriminator

- its fields define the request contract

- `apply()` defines the mutation

- its mutation is a
  [composition](https://datatracker.ietf.org/doc/html/rfc6902#section-4.3:~:text=This%20operation%20is%20functionally%20identical%20to%20a%20%22remove%22%20operation%20for%0A%20%20%20a%20value%2C%20followed%20immediately%20by%20an%20%22add%22%20operation%20at%20the%20same%0A%20%20%20location%20with%20the%20replacement%20value.)
  of other operations

That is why custom operations feel natural in JsonPatchX. They are not a
separate plugin language. They are the same abstraction as the standard
operations.

> Note also the [functional](https://docs.python.org/3/howto/functional.html)
> style of the `apply()`. JsonPatchX recommends you write mutations in this way
> to make them easier to reason about. For low-level mutations that require
> in-place semantics, try chaining stateless steps until the very end.

### Typed Pointers

`JSONPointer[T]` parses a JSON Pointer string up front. The target and its type
are enforced when you exercise it with `get()`, `add()`, or `remove()`.

For preflight checks, `is_gettable()`, `is_addable()`, and `is_removable()` ask
the same question without exception flow. For pointer relationships,
`is_parent_of()` and `is_child_of()` are available.

That is enough for this page. For the fuller targeting story, see
[Patch Targeting](patch-targeting.md).

### JSON-Native Types

JsonPatchX also provides helper types so you can reason about JSON rather than
Python's types:

- `JSONString`, `JSONNumber`, `JSONBoolean`, and `JSONNull` for primitives

- `JSONArray[T]` and `JSONObject[T]` for containers

- `JSONValue` for any of those

While you can opt out of using these types, JsonPatchX strongly recommends using
them. For example, `JSONNumber` is not merely an alias for `int | float` as it
rightfully rejects `bool`, which in Python is a subtype of `int`. Other types
may have more straightforward implementations now but are promised to remain
JSON-native even as the Python language evolves.

> Disclaimer: None of the custom operations below are directly importable from
> JsonPatchX. These are merely examples. <!-- TODO: For now. -->

## Intent-Based Operations

These operations make the contract say what the caller actually means, rather
than encoding that meaning indirectly through lower-level steps.

### Define `IncrementOp`

Suppose your client is always checking the current state of a resource just to
increment it by some amount with a `replace`. That's a good candidate for a
custom operation.

```python
from typing import Literal
from pydantic import Field
from jsonpatchx import JSONPointer, JSONValue, JSONNumber, OperationSchema, ReplaceOp

class IncrementOp(OperationSchema):
    op: Literal["increment"]
    path: JSONPointer[JSONNumber]
    amount: JSONNumber = Field(gt=0)

    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        return ReplaceOp(path=self.path, value=current + self.amount).apply(doc)
```

If every increment were expressed as a client-side read followed by `replace`:

- The communicated intent is collapsed into `replace`.
- The server can validate the `replace`, but not the higher-level intent that
  this was meant to be an increment.
- The read-then-replace flow is more vulnerable to stale reads and lost updates
  under concurrency.

Note the type safety:

- The `amount` must be a positive number
- The `path` must be a
  [JSON Pointer](https://datatracker.ietf.org/doc/html/rfc6901) string
- When `get()` is exercised, the `path` must resolve to a number.

As a reviewer, you don't really have to know much about the `JSONPointer` type
to read and understand this operation. And as a single class, it's easily
testable.

### Define `SwapOp`

You can express a swap with lower-level patch operations, but needing a
temporary path just to say "swap these two values" is a good sign the contract
wants its own operation. Here, the interesting part is less about type safety
and more about **input validation**.

Both paths can be perfectly valid JSON Pointers on their own and still be
invalid **together** for a swap. If one path is an ancestor of the other, then
the first replacement may restructure or overwrite the subtree that the second
path points into. In that case, the mutation is no longer well-defined.

That kind of rule belongs on the operation itself:

```python
from typing import Literal, Self, override
from pydantic import model_validator
from pydantic_core import PydanticCustomError
from jsonpatchx import JSONPointer, JSONValue, OperationSchema, ReplaceOp

class SwapOp(OperationSchema):
    op: Literal["swap"]
    a: JSONPointer[JSONValue]
    b: JSONPointer[JSONValue]

    @model_validator(mode="after")
    def _reject_proper_prefixes(self) -> Self:
        if self.a.is_parent_of(self.b):
            raise PydanticCustomError(
                "swap_path_conflict",
                "pointer '{ancestor}' cannot be an ancestor of pointer '{descendant}'",
                {"ancestor": "a", "descendant": "b"},
            )
        if self.b.is_parent_of(self.a):
            raise PydanticCustomError(
                "swap_path_conflict",
                "pointer '{ancestor}' cannot be an ancestor of pointer '{descendant}'",
                {"ancestor": "b", "descendant": "a"},
            )
        return self

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        value_a = self.a.get(doc)
        value_b = self.b.get(doc)

        doc = ReplaceOp(path=self.a, value=value_b).apply(doc)
        return ReplaceOp(path=self.b, value=value_a).apply(doc)
```

Courtesy of Pydantic, you get:

- `model_validator(mode="after")` to validate the operation as a whole, after
  its individual fields have already been parsed and validated.
- `PydanticCustomError` to raise a structured validation error instead of a
  generic `ValueError`. It gives you a stable error code, a message template,
  and named context values for the rendered message.

This is a good pattern when a custom operation needs to reject combinations of
inputs that are individually valid but invalid together.

> `SwapOp` can also be useful as a _component_ of a higher-level operation. For
> example, an operation like `PromoteItemOp` might swap adjacent items in a
> ranked list without reimplementing swap logic itself.

## Contract-Narrowing Operations

Not every custom operation introduces a new kind of mutation. Sometimes the win
is taking a broad standard operation and tightening its contract.

### Define `ReplaceNumberOp`

Use typed pointers when you want to narrow the type contract:

```python
from typing import Literal, override
from jsonpatchx import JSONPointer, JSONValue, OperationSchema, ReplaceOp
from jsonpatchx.types import JSONNumber

class ReplaceNumberOp(OperationSchema):
    op: Literal["replace_number"]
    path: JSONPointer[JSONNumber]
    value: JSONNumber

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        return ReplaceOp(path=self.path, value=self.value).apply(doc)
```

This works safely because `JSONPointer` is
[covariant](https://peps.python.org/pep-0483/#covariance-and-contravariance) in
its target type.

> In other words, a `JSONPointer[JSONNumber]` can be used anywhere a
> `JSONPointer[JSONValue]` is expected, because every JSON number is also a JSON
> value.

### Define `AddMissingKeyOp`

Contract narrowing can also be behavioral rather than just type-based.

`add` is a good example. Depending on the path, it may create a missing object
member, replace an existing value, or append into an array. That flexibility is
useful, but sometimes a caller means something more specific: add this object
key only if it does not already exist.

That is what `AddMissingKeyOp` expresses.

```python
from typing import Literal, override
from jsonpatchx import AddOp, JSONPointer, JSONValue, OperationSchema, PatchConflictError, TargetState, classify_state

class AddMissingKeyOp(OperationSchema):
    """AddOp but strictly for object key-value pair additions."""
    op: Literal["add_missing_key"]
    path: JSONPointer[JSONValue]
    value: JSONValue

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        state = classify_state(self.path.ptr, doc)

        if state is TargetState.OBJECT_KEY_MISSING:
            return AddOp(path=self.path, value=self.value).apply(doc)

        if state is TargetState.VALUE_PRESENT:
            raise PatchConflictError(f"path {self.path!r} already exists")

        raise PatchConflictError(f"add_missing_key requires a missing object key at {self.path!r}")
```

This example also shows a more advanced implementation tool: `classify_state()`.

Helpers such as `is_gettable()` and `is_addable()` are great when a yes-or-no
answer is enough. But sometimes an operation needs to distinguish _why_ a path
is usable or unusable. For example:

- the parent does not exist
- the parent exists but is not a container
- the object key is missing
- the value is already present
- the path points into an array instead of an object

`classify_state()` gives you that fine-grained view. Instead of collapsing all
failures into a single "not allowed" outcome, it lets a custom operation respond
differently to each case. This keeps the operation logic focused on intent
rather than reimplementing pointer resolution.

## Schema-Rich Operations

Because custom operations are ordinary Pydantic models, they can also express
rich OpenAPI directly.

### Define `ClampOp`

Sometimes, after a sequence of mutations, you want to guarantee that a numeric
result stays within an allowed range. The operation itself is straightforward,
but its schema has something useful to say: at least one of `min` or `max` must
be present.

```python
from typing import Literal, Self, override
from pydantic import ConfigDict, Field, model_validator
from pydantic_core import MISSING
from jsonpatchx import JSONPointer, JSONValue, OperationSchema, ReplaceOp
from jsonpatchx.types import JSONNumber

class ClampOp(OperationSchema):
    """Clamp a numeric value to an inclusive range."""

    model_config = ConfigDict(
        title="Clamp operation",
        validate_default=False,
        json_schema_extra={
            "description": "Clamp a numeric value at path to the inclusive range [min, max].",
            "anyOf":
                [
                    {"required": ["min"]},
                    {"required": ["max"]}
            ],
        },
    )
    op: Literal["clamp"]
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

This example is as much about contract design as it is about mutation logic.
Pydantic carries most of that contract surface:

- `ConfigDict(...)` to give the operation a title and description in generated
  schema.

- `Field(...)` metadata to document individual fields, including the typed
  pointer itself.

- `MISSING` so that `min` and `max` are optional by omission, not by
  nullability. That lets `model_fields_set` distinguish “not provided” from
  “provided with a numeric bound” without widening the wire contract to
  `number | null`.

- `json_schema_extra` to express richer schema rules directly, in this case that
  a request must provide
  [`anyOf`](https://json-schema.org/understanding-json-schema/reference/combining#anyOf)
  `min` or `max`.

The result is that the same model can drive parsing, validation, execution, and
documentation. The operation is not just something your server can run. It is
also something your API can describe clearly.

> I must admit, I didn't write that operation myself. I used JsonPatchX's
> [`examples/AGENTS.md`](https://github.com/angela-tarantula/jsonpatchx/blob/main/examples/AGENTS.md)
> context to give my coding agent everything it needed to produce it.

## Use Operation Instances Directly

In addition to patching with `list[dict]`s and JSON text, you can also use
instantiated Operation Schemas directly:

```python
patch = JsonPatch(
    [
        MultiplyOp(path="/foo/bar", scalar=2),
        IncrementOp(path="/foo/bar", amount=20),
        ClampOp(path="/foo/bar", max=100)
    ]
)
```

For this reason, you will usually want to default the `op` discriminator field:

```python
op: Literal["clamp"] = "clamp"
```

**Ordinarily**, this would produce misleading OpenAPI that no longer lists `op`
as required:

```json
{
  "properties": {
    "op": {
      "type": "string",
      "default": "clamp"
    }
  },
  "required": []
}
```

But JsonPatchX understands that `op` is a required discriminator over the wire,
so the guarantee is that `op` is always listed in `required` and that the
OpenAPI won't advertise a default, even when the runtime models can be
instantiated without `op`.

**JsonPatchX strives to provide a stable, standardized OpenAPI for PATCH
contracts that even SDKs can depend on.**
