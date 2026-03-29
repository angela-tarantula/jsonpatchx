# JsonPatchX

<!-- markdownlint-disable MD013 -->

[![Tests](https://img.shields.io/github/actions/workflow/status/angela-tarantula/jsonpatchx/python-tests.yml?branch=main&label=Tests&style=flat)](https://github.com/angela-tarantula/jsonpatchx/actions)
[![Codecov](https://codecov.io/github/angela-tarantula/jsonpatchx/graph/badge.svg)](https://codecov.io/github/angela-tarantula/jsonpatchx)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/angela-tarantula/jsonpatchx/badge)](https://scorecard.dev/viewer/?uri=github.com/angela-tarantula/jsonpatchx)

<!-- markdownlint-enable MD013 -->

JsonPatchX is a typed JSON Patch toolkit for building governed PATCH APIs in
Python.

It scales from simple patching to highly controlled API contracts:

- Plain JSON patching (`apply_patch`, `JsonPatch`)
- RFC-first FastAPI PATCH endpoints
- Expressive, governed PATCH APIs with route allow-lists, custom operations,
  model-bound contracts, and custom pointer behavior

## Install

Core library:

```sh
pip install jsonpatchx
```

FastAPI route helpers (`jsonpatchx.fastapi`):

```sh
pip install "jsonpatchx[fastapi]"
```

Note: `JsonPatchFor` is in the core package. The optional `fastapi` extra is for
route wiring/error-mapping helpers such as `JsonPatchRoute` and
`install_jsonpatch_error_handlers`.

## Quick Example

```python
from jsonpatchx import apply_patch

doc = {"name": "Ada", "roles": ["engineer"]}
patch = [
    {"op": "replace", "path": "/name", "value": "Ada Lovelace"},
    {"op": "add", "path": "/roles/-", "value": "maintainer"},
]

updated = apply_patch(doc, patch)
```

## Documentation

- User Guide (entry): `docs/index.md`
- Developer Reference (entry): `docs/developer-reference.md`
- API Reference (generated from source): `docs/api-reference.md`
- FastAPI demos: `examples/README.md`

Run local docs:

```sh
uv sync
uv run zensical serve
```

## License

MIT. See `LICENSE`.
