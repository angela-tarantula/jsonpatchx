# Custom Operations

Custom operations are worth adding when low-level RFC 6902 operations stop
reading like what the caller actually means.

That does not mean inventing a new mutation language for every API. Usually the
win is much simpler than that. A good custom op takes a mutation your clients
already keep expressing awkwardly, gives it a clear name, validates the right
things up front, and makes the contract easier to document.

Start small.

## Operations are just models with `apply()`

Before looking at a custom op, it helps to see how little machinery is involved.

A built-in operation such as `ReplaceOp` is conceptually this kind of shape:

```python
from typing import Literal

from jsonpatchx import JSONPointer, JSONValue, OperationSchema
from jsonpatchx.types import JSONValue as AnyJSONValue


class ReplaceOp(OperationSchema):
    op: Literal["replace"] = "replace"
    path: JSONPointer[AnyJSONValue]
    value: AnyJSONValue

    def apply(self, doc: JSONValue) -> JSONValue:
        return self.path.add(doc, self.value)
```

The real implementation may have more detail, but the important thing is the
shape:

- an operation is a Pydantic-backed model
- `op` is the discriminator
- its fields define the request contract
- `apply()` defines the mutation

That is why custom ops feel natural in JsonPatchX. They are not a separate
plugin language. They are the same abstraction as the built-ins.

## A first custom op: `IncrementOp`

This is a good first example because it stays small while showing why typed
pointers matter.

```python
from typing import Literal

from pydantic import Field

from jsonpatchx import JSONPointer, JSONValue, OperationSchema, ReplaceOp
from jsonpatchx.types import JSONNumber


class IncrementOp(OperationSchema):
    op: Literal["increment"] = "increment"
    path: JSONPointer[JSONNumber]
    amount: JSONNumber = Field(gt=0)

    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        return ReplaceOp(path=self.path, value=current + self.amount).apply(doc)
```

This is already doing a few useful things.

The payload says what the caller means. It is not pretending an increment is
just an arbitrary `replace`.

The `amount` field is validated before mutation starts.

And the path is not just “some string.” It is a pointer that is expected to
resolve to a JSON number.

That last part matters most.

## Typed pointers are part of the contract

`JSONPointer[T]` is not just a parsing helper. It lets the path itself
participate in the operation contract.

So this:

```python
path: JSONPointer[JSONNumber]
```

means more than “this field contains a JSON Pointer string.”

It means that when the pointer is used, the resolved value is expected to be a
JSON number.

That contract is enforced when the pointer resolves or writes:

- `get(doc)` resolves the path and validates the target against `T`
- `add(doc, value)` validates the value before writing it
- `remove(doc)` validates the existing target before removing it

A `JSONPointer` also comes with useful methods beyond simple resolution. It is a
subtype of `str`, so it behaves like a string when you need it to, but it also
has pointer-specific behavior such as `get(...)`, `add(...)`, `remove(...)`, and
relationship helpers such as `is_parent_of(...)`.

That makes custom ops easier to write and easier to validate correctly.

## Custom does not have to mean exotic

A custom op is often just a better contract for a mutation people already keep
trying to express with lower-level steps.

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

        return ReplaceOp(
            path=self.path,
            value=current.replace(self.old, self.new),
        ).apply(doc)
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
from typing import Literal, Self

from pydantic import ConfigDict, model_validator
from typing_extensions import override

from jsonpatchx import (
    JSONPointer,
    JSONValue,
    OperationSchema,
    OperationValidationError,
    ReplaceOp,
)


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
