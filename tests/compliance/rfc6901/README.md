# RFC 6901 Compliance Test Data

This directory keeps focused RFC 6901 coverage for JsonPatchX's default
`JSONPointer` implementation.

## Test Data Layout

- [`cases.py`](./cases.py): hand-curated RFC 6901 fixtures plus a few explicit
  non-standard cases that the default backend should reject.
- [`test_pointer.py`](./test_pointer.py): executes those cases through
  `JSONPointer.parse(...).get(...)`.

## Why These Tests Exist

Many JSON Pointer implementations are incomplete in edge cases or intentionally
loose. One example is this still-open fix in `python-json-pointer`:
[stefankoegl/python-json-pointer#76](https://github.com/stefankoegl/python-json-pointer/pull/76).
Some implementations also permit behavior outside RFC 6901, such as negative
array indices.

JsonPatchX treats RFC 6901 as the default pointer contract, so these tests lock
down escaping, traversal, and rejection behavior. Users can still swap the
default pointer backend if they prefer different semantics.

## Running Tests Locally

Run the pointer compliance tests normally:

```bash
uv sync
uv run pytest tests/compliance/rfc6901/test_pointer.py
```
