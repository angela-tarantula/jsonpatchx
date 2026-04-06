# Type System Notes

JsonPatchX leans hard on Python typing because patch documents are doing two
jobs at once:

- carrying data
- declaring what kinds of mutation are allowed

That pays off in clearer contracts, but it also means a few type-system details
are worth understanding.

## Strict JSON helper types are intentional

JsonPatchX ships JSON-specific helper types rather than leaning on broad Python
primitives everywhere:

- `JSONBoolean`
- `JSONNumber`
- `JSONString`
- `JSONNull`
- `JSONArray[T]`
- `JSONObject[T]`
- `JSONValue`

These types are strict on purpose.

That matters in patch contracts. A PATCH API usually wants to reject `"2"` where
the schema says number, and it should not quietly treat `True` as numeric JSON
just because Python lets `bool` subclass `int`.

Use these helper types when operation semantics care about JSON meaning rather
than generic Python values.

## `JSONPointer[T]` is a contract, not a promise

`JSONPointer[T]` tells JsonPatchX what kind of value the pointer is expected to
resolve.

It does not promise the path exists in every document.

That means this annotation:

```python
path: JSONPointer[JSONString]
```

says, “when this pointer is used, the target should behave like a JSON string.”

Existence and runtime shape are checked when pointer operations run.

That distinction keeps pointer annotations useful without pretending every
document already satisfies them.

## `JsonPatchFor` has two target modes

`JsonPatchFor` supports two kinds of target declarations:

- a Pydantic model class, for model-aware patching and result revalidation
- `Literal["SchemaName"]`, for raw JSON patch bodies that still need stable
  schema naming

Both are useful.

Use a model target when the patched result is a resource object with a real
schema.

Use a literal schema name when the endpoint works on free-form JSON, but you
still want OpenAPI components that read like deliberate API shapes instead of
anonymous arrays.

## Runtime-built registries are a typing trade-off

This pattern is useful:

```python
RuntimeRegistry = build_registry(enabled_ops)
PatchModel = JsonPatchFor[User, RuntimeRegistry]
```

It is also harder for static type checkers to reason about than a named alias
such as:

```python
type UserOps = StandardRegistry | IncrementOp
```

That is not a flaw in the idea. It is just the trade-off between runtime
flexibility and static readability.

A good rule of thumb:

- use named aliases for stable, human-facing contracts
- use runtime-built registries at startup boundaries where rollout flexibility
  matters more than perfect static inference

## Keep runtime complexity at the edges

When typing starts to feel strained, the usual fix is not “stop using types.”

The better fix is usually:

- keep route-facing contracts simple and named
- keep runtime composition near startup or configuration code
- keep custom operations small and explicit
- avoid inventing one giant generic abstraction that tries to model every PATCH
  pattern at once

That keeps the type system working for you instead of becoming part of the
problem.
