# JsonPatchX

<!-- markdownlint-disable MD013 -->

[![Tests](https://img.shields.io/github/actions/workflow/status/angela-tarantula/jsonpatchx/python-tests.yml?branch=main&label=Tests&style=flat)](https://github.com/angela-tarantula/jsonpatchx/actions)
[![Codecov](https://codecov.io/github/angela-tarantula/jsonpatchx/graph/badge.svg)](https://codecov.io/github/angela-tarantula/jsonpatchx)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/angela-tarantula/jsonpatchx/badge)](https://scorecard.dev/viewer/?uri=github.com/angela-tarantula/jsonpatchx)
[![Contributor Covenant](https://img.shields.io/badge/Contributor%20Covenant-3.0-fbab2c.svg)](CODE_OF_CONDUCT.md)

<!-- markdownlint-enable MD013 -->

JsonPatchX is a Python toolkit for JSON patching, from standard
[RFC 6902](https://datatracker.ietf.org/doc/html/rfc6902) to governed PATCH APIs
and agent-friendly patch toolkits. Tested against the
[RFC 6902 Compliance Test Suite](https://github.com/json-patch/json-patch-tests).

## Use It Three Ways

- **Standard JSON Patch in Python**: parse, validate, and apply ordinary RFC
  6902 patch documents.
- **Governed PATCH APIs**: add custom operations, typed targeting, endpoint
  controls, and OpenAPI generated from the same operations.
- **Agentic Patching**: publish reviewed operations as typed Python models and
  OpenAPI schemas for coding agents to discover and use.

## Documentation

Read the docs:
[https://angela-tarantula.github.io/jsonpatchx](https://angela-tarantula.github.io/jsonpatchx)

If you are deciding where to start:

- [User Guide](https://angela-tarantula.github.io/jsonpatchx/user-guide/getting-started/):
  read in order, starting with plain RFC 6902 patching.
- [About](https://angela-tarantula.github.io/jsonpatchx/about/about/): why the
  project exists, the three main use cases, and the model layer behind them.
- [Developer Reference](https://angela-tarantula.github.io/jsonpatchx/developer-reference/developer-reference/):
  contributor and extension details.
- [API Reference](https://angela-tarantula.github.io/jsonpatchx/api-reference/api-reference-public/):
  generated public API surface.

<!--

## Installation

```sh
pip install jsonpatchx
```
-->

## Examples

### 1. Standard RFC 6902

```python
from jsonpatchx import JsonPatch

doc = {"name": "Ada", "roles": ["engineer"]}

patch = JsonPatch.from_string(
    """
    [
      {"op": "replace", "path": "/name", "value": "Ada Lovelace"},
      {"op": "add", "path": "/roles/-", "value": "maintainer"}
    ]
    """
)

updated = patch.apply(doc)
```

### 2. The FastAPI Contract

```python
from fastapi import FastAPI
from pydantic import BaseModel, EmailStr
from jsonpatchx import JsonPatchFor

class User(BaseModel):
    id: int
    email: EmailStr
    active: bool

app = FastAPI()

@app.patch("/users/{user_id}", response_model=User)
def patch_user(user_id: int, patch: JsonPatchFor[User]) -> User:
    user = load_user(user_id)
    updated = patch.apply(user)
    save_user(user_id, updated)
    return updated
```

> **Note**: For custom operations, JSONPath targeting, route-level controls, and
> more, see the [User Guide](https://angela-tarantula.github.io/jsonpatchx/).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for local setup, checks, docs preview,
and pull request expectations.

Use [Discussions](https://github.com/angela-tarantula/jsonpatchx/discussions)
for project-specific design conversation,
[issues](https://github.com/angela-tarantula/jsonpatchx/issues) for concrete
bugs or proposed work, and the broader
[json-patch2](https://github.com/json-patch/json-patch2) forum for standards
discussion.

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for more information.

## Contact

Angela Liss - [chamsester@gmail.com](mailto:chamsester@gmail.com)

Project Link:
[https://github.com/angela-tarantula/jsonpatchx](https://github.com/angela-tarantula/jsonpatchx)

## Acknowledgements

Thanks to these foundational projects:

- [Pydantic](https://docs.pydantic.dev/latest/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [python-json-pointer](https://github.com/stefankoegl/python-json-pointer)
- [python-jsonpath](https://github.com/jg-rp/python-jsonpath)

And to these excellent alternatives:

- [py_yyjson](https://tkte.ch/py_yyjson/#patch-a-document)
- [json-merge-patch](https://github.com/OpenDataServices/json-merge-patch)
- [python-json-patch](https://github.com/stefankoegl/python-json-patch)
