# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Companion Guides

- [AGENTS.md](AGENTS.md): house style for docs structure, Google-style
  docstrings (Zensical-rendered), and `CHANGELOG.md` writing rules. Read it
  before editing docs, public docstrings, or the changelog.
- [examples/AGENTS.md](examples/AGENTS.md): guidance for authoring custom
  operations. The `tests/agents/` fixtures are manual prompt-only regression
  checks for that file (not part of pytest).
- [CONTRIBUTING.md](CONTRIBUTING.md): full local setup; the commands below are a
  quick reference.

## Common Commands

This project uses [uv](https://docs.astral.sh/uv/) and
[prek](https://github.com/j178/prek).

```sh
uv sync                       # install all dev deps (after `git submodule update --init`)
uv run pytest -v              # full test suite
uv run pytest tests/unit/standard -v             # one directory
uv run pytest tests/unit/standard/test_apply.py::test_name   # one test
uv run pytest -m integration                     # marker: integration | contract
uv run mypy . --no-incremental  # strict type-check (config in pyproject.toml)
uv run ruff format              # format
uv run prek run --all-files      # full local hook set (lint, markdown, yaml, codespell, ...)
uv run prek run <hook-id> --all-files
uv run zensical serve           # docs preview
uv run zensical build --clean   # build docs
uv run python scripts/update_openapi_snapshots.py   # regenerate OpenAPI contract snapshots
```

`pyproject.toml` sets `filterwarnings = ["error"]`: any unexpected warning fails
the suite. Coverage `fail_under = 90`.

## Architecture

JsonPatchX is a Pydantic-based JSON Patch (RFC 6902) library with typed JSON
Pointer / JSONPath targeting and FastAPI integration. The package layout maps
directly to a layered design; read modules in this order:

1. **`types.py`**: `JSONValue` recursive alias and JSON shape predicates.
2. **`backend.py`**: `JSONPointer[T]` / `JSONSelector[T]` runtime contracts.
   Wraps `python-json-pointer` and `python-jsonpath`. `T` is enforced at
   _resolve_ time, not just statically; this is what makes "type-gated"
   semantics possible (e.g. a `remove` may fail because the resolved value
   doesn't match `T`). `DEFAULT_POINTER_CLS` / `DEFAULT_SELECTOR_CLS` are the
   defaults used when models don't pick a backend explicitly.
3. **`schema.py`**: `OperationSchema`, the abstract Pydantic base for every
   operation. Subclasses declare `op: Literal["..."]` plus typed pointer fields.
   `_apply_ops` is the per-op driver.
4. **`builtins.py`**: the six RFC 6902 ops (`AddOp`, `RemoveOp`, `ReplaceOp`,
   `MoveOp`, `CopyOp`, `TestOp`) implemented as `OperationSchema` subclasses.
5. **`registry.py`**: `StandardRegistry` + `_RegistrySpec`. Builds a
   discriminated `Annotated[Union[...], Field(discriminator="op")]` keyed on
   `op` from a set of `OperationSchema` subclasses, so incoming patch JSON
   parses to the correct concrete op. `StandardRegistry` is the built-in
   typeform.
6. **`standard.py`**: `JsonPatch` (the public sequence type) and `apply_patch`.
   The "behavioral center": defines copy/mutation semantics (`inplace=False`
   deep-copies; `inplace=True` is non-transactional and may leave partial
   mutations on failure) and error semantics (`PatchError` subclasses propagate;
   unexpected exceptions are wrapped with op index + payload).
7. **`pydantic.py`**: `JsonPatchFor[T]`: a `JsonPatch` parameterized by a target
   Pydantic model so the patched document round-trips through `T`'s validation.
8. **`fastapi.py`**: request-body integration and OpenAPI schema emission for
   `JsonPatchFor[T]` route params.
9. **`exceptions.py`**: public exception hierarchy rooted at `PatchError`, plus
   structured `PatchFailureDetail`.

Public surface is reexported from `jsonpatchx/__init__.py`; treat anything not
in `__all__` as private.

### Adding or changing operations

- New built-in: subclass `OperationSchema`, add `Literal["..."]` for `op`,
  implement `apply`, then add it to `StandardRegistry` /
  `_STANDARD_REGISTRY_SPEC`.
- Custom op authoring (downstream user-facing): the canonical guidance lives in
  `examples/AGENTS.md`; keep that file and any changes consistent with the
  actual `OperationSchema` API.
- Pointer typing is part of the contract: widen to `JSONValue` for permissive
  ops; narrow `T` to gate behavior.

### Tests

- `tests/unit/<module>/`: mirrors the package layout.
- `tests/integration/`: `core/` cross-module flows; `fastapi/` runtime
  integration (uses `httpx`, `uvicorn`).
- `tests/contract/openapi/`: OpenAPI snapshot tests; regenerate via
  `scripts/update_openapi_snapshots.py`.
- `tests/compliance/rfc6901|rfc6902|rfc9535/`: external compliance suites (some
  pulled via Git submodule; run `git submodule update --init` first).
- `tests/agents/`: manual prompt-only checks for `examples/AGENTS.md`; see its
  `README.md`. Not run by pytest.

## Conventions

- Python 3.12+; `mypy` runs in `strict` mode with extra error codes
  (`explicit-any`, `exhaustive-match`, `no-any-return`, ...). New code must
  type-check clean; don't loosen the config to silence errors.
- Public docstrings follow the Google-style sections defined in
  [AGENTS.md](AGENTS.md) (`Arguments`, `Returns`, `Raises`, `Examples`,
  `Notes`).
- Docstring opening sentences use imperative mood: "Check whether", not "Checks
  if".
- `Returns` lines end with "`True` if ..., `False` otherwise" (not "otherwise
  `False`").
- Em dashes are strictly forbidden in docs and docstrings. Use a colon,
  semicolon, or comma instead.
- `CHANGELOG.md` is public-API focused; see [AGENTS.md](AGENTS.md). Don't log
  internal refactors there. Any addition, removal, or breaking change to the
  public API (`__all__`) requires a changelog entry.
- Prefer editing existing modules over adding new ones; the layering above is
  intentional.
- When changing what exception a method raises, update the `Raises` section of
  every caller, then every caller of those callers, and so on until the call
  tree is exhausted. Use grep to find callers across the whole codebase; do not
  rely on memory. Boolean helpers with no `Raises` section still need one added
  if an exception now propagates through them instead of being swallowed. After
  completing the update, report the full caller hierarchy back to the user so
  they can verify each level was handled correctly.
- Before assuming a docstring is visible on an API reference page, check that
  page's `docs/api-reference/*.md` file for its `filters:` option.
  Module-specific pages use `filters: ["!^_"]`, which drops every
  underscore-prefixed name, including dunders (`__init_subclass__`, `__init__`,
  `__str__`, etc.). The Exports page (`api-reference-public.md`) has no filter,
  so documented dunders do appear there. If key information lives only in a
  filtered method's docstring, it must be duplicated in the class docstring. To
  re-include specific dunders while keeping the general exclusion, put `"!^_"`
  first and the dunder include patterns after it — mkdocstrings uses
  last-match-wins semantics.
