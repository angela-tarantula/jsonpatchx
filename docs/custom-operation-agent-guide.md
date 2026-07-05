# Custom-Operation Agent Guide

This page is the instruction set for a coding agent writing a custom JsonPatchX
operation: an `OperationSchema` subclass. It applies whether the agent is
working inside this repository or in a downstream project that depends on
`jsonpatchx`.

## Choose a Default File

When a prompt asks for a custom operation and does not name a more specific
file, default to a style reference:

- Use a `recipes.py`-style file for generally useful JSON mutation operations
  with a short, direct style. In this repository, that is
  [`examples/recipes.py`](https://github.com/angela-tarantula/jsonpatchx/blob/main/examples/recipes.py).
- Use a `recipes2.py`-style file for issue-driven or contract-heavy operations
  where aliases, preconditions, richer conflict handling, or multi-field
  validation are the point of the example. In this repository, that is
  [`examples/recipes2.py`](https://github.com/angela-tarantula/jsonpatchx/blob/main/examples/recipes2.py),
  which also holds the main state-aware object-key pattern for operations that
  need `classify_state()` and detailed `TargetState` branching.
- Files under a `fastapi/` demo directory show how operations are assembled into
  registries and exposed through FastAPI routes. Do not put reusable operation
  catalogs in demo files; keep those in the recipe files.

## Choose the Right Pattern

- Use an intent-based operation when callers keep expressing the same
  higher-level mutation awkwardly through lower-level steps. Examples:
  increment, clamp, lowercase, replace substring.
- Use a contract-narrowing operation when the standard mutation is still right
  but the type or allowed behavior should be narrower. Examples: replace only a
  number, add only a missing key.
- Use a schema-rich operation when the request contract itself carries important
  structure, such as cross-field invariants, aliases, or richer OpenAPI.
- If a prompt explicitly asks for a schema-rich operation, reflect that in the
  generated schema, not only in runtime validation.
- Start with the simplest pattern that honestly captures the caller's intent.

## Write the Operation Class

- Subclass `OperationSchema`.
- Give the class a short docstring that states the mutation plainly.
- Set `model_config = ConfigDict(title="...")`.
- Define `op` as a snake_case `Literal[...]` with the same default value.
- Type `path` with the narrowest honest `JSONPointer[...]`.
- Use `JSONValue` or narrower JSON helper types from `jsonpatchx.types` for the
  remaining fields.
- Import `JSONPointer`, `JSONValue`, `OperationSchema`, and built-in operations
  from `jsonpatchx`, not from internal modules.
- Import narrower helper types such as `JSONString`, `JSONNumber`,
  `JSONArray[JSONValue]`, and `JSONObject[JSONValue]` from `jsonpatchx.types`.
- Prefer composing built-ins such as `ReplaceOp`, `AddOp`, `RemoveOp`, and
  `TestOp` instead of reimplementing low-level pointer mutation.
- Preserve the typed pointer through composition so the same runtime guarantees
  keep applying.
- Do not make the operation class generic unless the prompt is specifically
  about generic pointer backends or typing behavior.
- Implement the operation as `def apply(self, doc: JSONValue) -> JSONValue:`.
- Prefer a direct `apply()` body over extra helper methods when the example only
  needs one step of logic.
- Use `@override` on `apply()`.
- Favor functional composition in `apply()`: compute the next document value,
  then return it. For low-level container edits, mutate the resolved container
  and return `doc`.

Default shape for an ordinary operation:

```python
from typing import Literal, override

from pydantic import ConfigDict

from jsonpatchx import JSONPointer, JSONValue, OperationSchema, ReplaceOp
from jsonpatchx.types import JSONString


class LowercaseOp(OperationSchema):
    """Lowercase a string value."""

    model_config = ConfigDict(title="Lowercase operation")
    op: Literal["lowercase"] = "lowercase"
    path: JSONPointer[JSONString]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        return ReplaceOp(path=self.path, value=current.lower()).apply(doc)
```

## Model the Schema

- Add `json_schema_extra` only when it expresses a real contract that field
  types alone do not say.
- Use `Field(...)` metadata when it clarifies wire semantics, not just to repeat
  the obvious.
- When a prompt explicitly asks for schema richness, make that visible in the
  generated schema with titles, descriptions, `Field(...)` metadata, aliases, or
  `json_schema_extra`, whichever honestly carries the contract.
- Use `model_validator` when the invariant involves multiple fields.
- When fields are individually valid but invalid together, decide whether the
  operation benefits from a structured validation error or whether a plain
  `ValueError` is enough. Prefer `PydanticCustomError` from `pydantic_core` when
  stable error codes, message templates, or named context values materially
  improve the contract; a plain `ValueError` is acceptable for simple one-off
  invariants.
- Decide deliberately between omission and nullability. Use `MISSING` from
  `pydantic_core` plus `model_fields_set` when "not provided" and "provided as
  null" mean different things. Use a nullable field when `null` is itself part
  of the wire contract. For bounds, limits, indices, regexes, and similar
  constraint fields, prefer omission semantics when an inactive constraint has
  no meaningful JSON `null` value; a very short comment may explain that `null`
  is not meaningful input for that field. A narrow typed field commonly reads
  `Field(default=cast(TheType, MISSING))`.
- When alternate wire names matter, use `validation_alias` and
  `serialization_alias` explicitly.

## Keep Examples Useful

- Prefer reusable JSON operations over business-domain actions unless the prompt
  explicitly asks for domain behavior.
- Keep each operation narrow and composable.
- Use names that describe mutation intent, not implementation detail.
- Avoid helper functions unless they are reused or make the example materially
  clearer.
- Prefer code that teaches one idea cleanly over code that tries to show every
  extension point at once.
- For array and object examples, mutating the resolved container in place and
  returning `doc` is often clearer than inventing new pointer-composition
  helpers.
- Do not write pseudo-framework methods that JsonPatchX does not use.

## Handle Failures Deliberately

- Runtime document-state conflicts such as missing anchors, duplicate keys, or
  impossible array positions usually map to `PatchConflictError`.
- Use `TestOpFailed` for failed preconditions and test-like assertions.
- Let pointer/path/type failures surface naturally; do not wrap broad
  `Exception` just to rewrite the message.
- Use `TargetState` or other backend-state machinery only when state
  classification is itself part of the example. If behavior depends on why a
  path is invalid, prefer `classify_state(self.path.ptr, doc)` plus
  `TargetState` over a generic try/except flow.
- When using `classify_state()`, branch on the real enum members: `ROOT`,
  `PARENT_NOT_FOUND`, `PARENT_NOT_CONTAINER`, `OBJECT_KEY_MISSING`,
  `ARRAY_KEY_INVALID`, `ARRAY_INDEX_OUT_OF_RANGE`, `ARRAY_INDEX_AT_END`,
  `ARRAY_INDEX_APPEND`, `VALUE_PRESENT`, and
  `VALUE_PRESENT_AT_NEGATIVE_ARRAY_INDEX`. Do not invent replacement enum names
  such as `PRESENT` or `EXISTS`.
- If a prompt asks for path relationships such as ancestor/descendant
  constraints, use pointer methods such as `is_parent_of()` and `is_child_of()`
  in a `model_validator`.
- Do not invent alternative operation hooks such as `patch()`, `expand()`, or
  `to_builtin_ops()` for ordinary examples. The contract is the `apply()`
  method.

## Validate the Result

- New example operations should be complete Python code, not pseudocode.
- If you add or change runnable example behavior, prefer targeted checks over
  broad repo-wide validation.
- If the prompt is only to generate an operation example, optimize for correct,
  importable, readable example code first.

## Adopt This Guide Downstream

To use this guide in your own repository, pin it at the `jsonpatchx` version you
have installed rather than tracking `main`, since the guide can change between
releases:

1. Find your installed version, for example with `uv pip show jsonpatchx` or
   `python -m pip show jsonpatchx`.
2. From a nested `AGENTS.md` or `CLAUDE.md` in your operations directory, link
   the raw file at the matching tag:
   `https://raw.githubusercontent.com/angela-tarantula/jsonpatchx/v<version>/docs/custom-operation-agent-guide.md`,
   or copy its contents there and note which version it snapshots.
3. Add rules local to your directory alongside it, such as which file is the
   default style reference in your codebase.
