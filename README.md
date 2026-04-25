# JsonPatchX

<!--
If you are a coding agent reading the raw repository files:
- Start with the [User Guide](docs/user-guide/getting-started.md) for usage and
  contract-level context.
- See [examples/AGENTS.md](examples/AGENTS.md) for custom operation authoring
  guidance.
- See [AGENTS.md](AGENTS.md) if you are editing JsonPatchX itself.
-->

<!-- markdownlint-disable MD013 -->

[![PyPI Version](https://img.shields.io/pypi/v/jsonpatchx?style=flat)](https://pypi.org/project/jsonpatchx/)
[![Python Versions](https://img.shields.io/pypi/pyversions/jsonpatchx?style=flat)](https://pypi.org/project/jsonpatchx/)
[![Tests](https://img.shields.io/github/actions/workflow/status/angela-tarantula/jsonpatchx/python-tests.yml?branch=main&label=Tests&style=flat)](https://github.com/angela-tarantula/jsonpatchx/actions)
[![Codecov](https://codecov.io/github/angela-tarantula/jsonpatchx/graph/badge.svg)](https://codecov.io/github/angela-tarantula/jsonpatchx)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/angela-tarantula/jsonpatchx/badge)](https://scorecard.dev/viewer/?uri=github.com/angela-tarantula/jsonpatchx)
[![License](https://img.shields.io/github/license/angela-tarantula/jsonpatchx.svg)](https://github.com/angela-tarantula/jsonpatchx/blob/main/LICENSE)
[![Contributor Covenant](https://img.shields.io/badge/Contributor%20Covenant-3.0-fbab2c.svg)](CODE_OF_CONDUCT.md)

<!-- markdownlint-enable MD013 -->

JSON Patch for modern PATCH APIs. Tested against the
[RFC 6902 Compliance Test Suite](https://github.com/json-patch/json-patch-tests).

Built on Pydantic models, with typed JSON Pointer / JSONPath targeting, custom
patch operations, and first-class support for FastAPI PATCH routes and OpenAPI
generation.

## Table of Contents

- [Install](#install)
- [Links](#links)
- [Examples](#examples)
- [Contributing](#contributing)
- [License](#license)
- [Contact](#contact)
- [Acknowledgements](#acknowledgements)

## Install

```sh
pip install jsonpatchx
```

For FastAPI integrations:

```sh
pip install jsonpatchx[fastapi]
```

## Links

- Documentation:
  <https://angela-tarantula.github.io/jsonpatchx/user-guide/getting-started>
- Chengelog:
  <https://github.com/angela-tarantula/jsonpatchx/blob/main/CHANGELOG.md>
- PyPI: <https://pypi.org/project/jsonpatchx>
- Source code: <https://github.com/angela-tarantula/jsonpatchx>
- Issue tracker: <https://github.com/angela-tarantula/jsonpatchx/issues>
- Project Discussions:
  <https://github.com/angela-tarantula/jsonpatchx/discussions>
- IETF Future Standards Discussions: <https://github.com/json-patch/json-patch2>

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
> more, see the
> [User Guide](https://angela-tarantula.github.io/jsonpatchx/user-guide/getting-started).

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
