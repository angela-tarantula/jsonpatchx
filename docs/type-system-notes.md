# Type System Notes

JsonPatchX aims for JSON semantics over Python coercion semantics.

## JSON Helpers Are Strict

- `JSONNumber` is `int | float` but excludes `bool`
- non-finite numbers (`NaN`, `Infinity`, `-Infinity`) are rejected
- `JSONValue` enforces strict JSON-compatible structures

## Why This Matters

Pydantic models type your data model, while JsonPatchX types operation intent
and pointer targets.

That lets you reject operational behavior early, even before domain-level
validation would fail.
