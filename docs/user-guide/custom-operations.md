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
from pydantic import ConfigDict
from jsonpatchx import AddOp, JSONPointer, JSONValue, OperationSchema, PatchConflictError, classify_state

class AddMissingKeyOp(OperationSchema):
    """AddOp but strictly for object key-value pair additions."""
    op: Literal["add_missing_key"]
    path: JSONPointer[JSONValue]
    value: JSONValue

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        state = classify_state(self.path.ptr, doc) # TODO: make better

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
> error messages is available in the recipes folder # TODO should you want to
> use a production-ready version of this.

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

## Custom does not have to mean exotic

A custom operation is often just a better contract for a mutation people already
keep trying to express with lower-level steps.

`replace_substring` is a good example:

```python
from typing import Literal

from jsonpatchx import (
    JSONPointer,
    JSONValue,
    OperationSchema,
    PatchConflictError,
    ReplaceOp,
)
from jsonpatchx.types import JSONString


class ReplaceSubstringOp(OperationSchema):
    op: Literal["replace_substring"] = "replace_substring"
    path: JSONPointer[JSONString]
    old: JSONString
    new: JSONString

    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        if self.old not in current:
            raise PatchConflictError(f"{self.old!r} is not in {current!r}")

        substituted = current.replace(self.old, self.new)
        return ReplaceOp(path=self.path, value=substituted).apply(doc)
```

This is still “just a replace” in one sense.

But the contract is much better:

- the request states intent directly
- the path is type-gated as a string target
- the failure mode is specific and meaningful
- the route can choose to advertise this op explicitly instead of burying the
  behavior in application code

That is the sort of extension JsonPatchX is trying to encourage.

## A more expressive example: `SwapOp`

`swap` is a good second example because it shows something that is genuinely
awkward to express with plain RFC operations.

You can simulate a swap with low-level steps, but the patch gets clumsy fast.
You usually need a temporary location, careful sequencing, and more explanation
than the operation itself should require.

A dedicated `swap` op is much clearer.

```python
from typing import Literal, Self, override
from pydantic import ConfigDict, model_validator
from jsonpatchx import JSONPointer, JSONValue, OperationSchema, OperationValidationError, ReplaceOp

class SwapOp(OperationSchema):
    model_config = ConfigDict(
        title="Swap operation",
        json_schema_extra={
            "description": (
                "Swap the values at paths 'a' and 'b'. "
                "Paths 'a' and 'b' may not be ancestors of each other."
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

        doc = ReplaceOp(path=self.a, value=value_b).apply(doc)
        return ReplaceOp(path=self.b, value=value_a).apply(doc)
```

This example is worth studying for a different reason than `increment`.

It shows what a well-documented operation looks like:

- the schema has a real title
- the schema has a real description
- important invariants are validated before mutation starts
- the implementation composes existing operations instead of inventing a second
  write engine

That last point is a good habit. Custom operations should usually reuse the
library’s existing mutation semantics where possible.

## JSON helper types are worth using

JsonPatchX includes strict JSON helper types for exactly this sort of operation
design:

- `JSONBoolean`
- `JSONNumber`
- `JSONString`
- `JSONNull`
- `JSONArray[T]`
- `JSONObject[T]`
- `JSONValue`

These keep operation contracts aligned with JSON semantics rather than loose
Python coercions. For custom ops, that usually leads to better validation and
clearer schema.

## Good custom operations tend to have the same shape

A custom operation usually ages well when it does a few things clearly:

- it names a real domain mutation
- its payload is small and obvious
- the important invariants are validated before mutation
- its conflict behavior is specific
- it composes cleanly with the rest of the registry

That last part matters too. A custom op should feel like one more operation your
route can choose to advertise, not like a separate subsystem.

## Expose custom operations through registries

Defining a custom op does not mean every route should accept it.

That is what registries are for.

```python
from jsonpatchx import JsonPatchFor, StandardRegistry

type BillingAdminOps = StandardRegistry | IncrementOp | SwapOp

BillingAdminPatch = JsonPatchFor[BillingAccount, BillingAdminOps]
```

That keeps the extension explicit.

A route either supports `increment` and `swap`, or it does not. The request
model, the OpenAPI schema, and the runtime parser all agree.

The next page moves from operation semantics to targeting semantics with
`JSONSelector`.

Most custom mutations are not going to be a sequence of standard operations, and
that's okay. When mutations have to do a little more "work", JsonPatchX keeps it
as frictionless as possible.
