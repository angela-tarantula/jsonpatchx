# Custom Operations

Custom operations are worth adding when low-level operations stop reading like
what the caller actually means.

That does not mean inventing a new mutation language for every API. Usually the
win is much simpler than that. A good custom operation takes a mutation your
clients already keep expressing awkwardly, gives it a clear name, validates the
right things up front, and makes the contract easier to document.

Start small.

## Operations Should be Simple

Before looking at a custom operation, it helps to see how little machinery is
involved.

A built-in operation such as `ReplaceOp` is conceptually this kind of shape:

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

## Your First Custom Operation: `IncrementOp`

> Disclaimer: none of the custom operations on this page are directly importable
> from JsonPatchX. These are merely examples.

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

Note the type safety:

- The `amount` must be a positive number

- The `path` must be a
  [JSON Pointer](https://datatracker.ietf.org/doc/html/rfc6901) string

- When `get()` is exercised, the `path` must resolve to a number.

As a reviewer, you don't really have to know much about the `JSONPointer` type
to read and understand this operation. And as a single class, it's easily
testable.

## Typed Pointers

Let's clear up exactly what you can expect from typed pointers.

### What `JSONPointer` Promises

The most important thing to understand is that `JSONPointer` enforces valid JSON
Pointer strings, but it does not promise that the path exists or resolves to the
correct type **unless you say so**.

The type contract is enforced when the pointer resolves or writes:

- `get(doc)` resolves the path and validates the target against `T`

- `add(doc, value)` validates the value before writing it

- `remove(doc)` validates the existing target before removing it

### What `JSONPointer` Uses

JsonPatchX provides a suite of helper types so you can reason about JSON rather
than Python's types:

- `JSONString`, `JSONNumber`, `JSONBoolean`, and `JSONNull` for primitives

- `JSONArray[T]` and `JSONObject[T]` for containers

- `JSONValue` for any of those

> While you can opt out of using these types, JsonPatchX strongly recommends
> using them. For example, `JSONNumber` is not merely an alias for `int | float`
> as it rightfully rejects `bool`, which in Python is a subtype of `int`. Other
> types may have more straightforward implementations but should be considered
> more future-proof as Python itself evolves.

### What `JSONPointer` Provides

The `JSONPointer` type itself is expressive with what you can do.

- As a subtype of `str`, it inherits all `str` behavior. This is also the
  [correct model](https://datatracker.ietf.org/doc/html/rfc6901#:~:text=A%20JSON%20Pointer%20is%20a%20Unicode%20string).

- `is_gettable()`, `is_addable()`, and `is_removable()` let you ask “would this
  succeed?” without the try-except ceremony.

- `is_parent_of()` and `is_child_of()` let custom operations validate pointer
  relationships before mutation starts. That is exactly the kind of guard you
  want in operations like `move` and `swap`.

- `parts` is a property that gives you the unescaped path components, which is
  often easier to reason about than the raw pointer string.

- If you ever need different syntax, `JSONPointer[T, CustomPointer]` lets you
  keep the same typed surface while substituting your preferred implementation.
  The `ptr` property exposes the underlying implementation for advanced use
  cases.

## Your Second Custom Operation: `SwapOp`

You can express a swap with lower-level patch operations, but it stops reading
like what the caller actually means. Here, the interesting part is less about
type safety and more about **input validation**.

Both paths can be perfectly valid JSON Pointers on their own and still be
invalid **together** for a swap. If one path is an ancestor of the other, then
the first replacement may restructure or overwrite the subtree that the second
path points into. In that case, the mutation is no longer well-defined.

That kind of rule belongs on the operation itself:

```python
from typing import Literal, Self, override
from pydantic import model_validator, PydanticCustomError
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

## Your Third Custom Operation: `AddMissingKeyOp`

Not every custom operation has to introduce a brand-new kind of mutation.
Sometimes the win is simply taking a broad standard operation and giving it a
narrower, safer contract.

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

> Note: An implementation of `AddMissingKeyOp` with more structured and detailed
> error messages is available in the recipes folder should you want to use a
> production-ready version of this.

## Your Fourth Custom Operation: `ReplaceNumberOp`

Typed pointers are also useful when you want a custom operation to be _more
specific_ than the built-in operation it delegates to.

`ReplaceOp` works on any JSON value:

- `path: JSONPointer[JSONValue]`
- `value: JSONValue`

But a custom operation can narrow that contract. For example, if an operation
only makes sense for numbers, it can require a numeric pointer and a numeric
replacement value up front.

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

Here, `ReplaceNumberOp` wraps a tighter contract around `ReplaceOp`.

This works safely because `JSONPointer` is
[covariant](https://peps.python.org/pep-0483/#covariance-and-contravariance) in
its target type.

In other words, a `JSONPointer[JSONNumber]` can be used anywhere a
`JSONPointer[JSONValue]` is expected, because every JSON number is also a JSON
value.

That lets a custom operation expose a narrower contract while still delegating
to a broader built-in operation.

## Your Fifth Custom Operation: `ClampOp`

The previous examples focused on typing, validation, and mutation semantics. One
more benefit is worth seeing directly: custom operations can also produce rich
OpenAPI because they are ordinary Pydantic models.

A clamp operation is a good fit for that. Sometimes, after a sequence of
mutations, you want to guarantee that a numeric result stays within an allowed
range. The operation itself is straightforward, but its schema has something
useful to say: at least one of `min` or `max` must be present.

```python
from typing import Literal, Self, override
from pydantic import ConfigDict, Field, model_validator
from pydantic.experimental.missing_sentinel import MISSING
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

This example is intentionally as much about the schema as it is about the
mutation.

Courtesy of Pydantic, you get:

- `ConfigDict(...)` to give the operation a title and description in generated
  schema.

- `json_schema_extra` to express richer schema rules directly, in this case that
  a request must provide `min`, `max`, or both.

- `Field(...)` metadata to document individual fields, including the typed
  pointer itself.

The result is that the same model can drive parsing, validation, execution, and
documentation. The operation is not just something your server can run. It is
also something your API can describe clearly.

> I must admit, I didn't write that operation myself. I used JsonPatchX's
> AGENTS.md context to give my coding agent everything it needed to produce it.

## One More Ergonomic Refinement

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

For this reason, you will usually want to default discriminator fields such as
`op`, for example:

```python
op: Literal["clamp"] = "clamp"
```

JsonPatchX won't let these ergonomic defaults negatively affect your OpenAPI.
For example, you **won't** have to see this in your PATCH schema:

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

> The `default` key is always excluded for `op`, and `op` will always be listed
> inside `required`.

JsonPatchX strives to provide a stable, standardized OpenAPI for PATCH contracts
that even SDKs can depend on.
