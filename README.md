# JsonPatchX

_A framework for governed PATCH APIs in Python. Powered by Pydantic. FastAPI
native._

<!-- markdownlint-disable MD013 -->

[![Tests](https://img.shields.io/github/actions/workflow/status/angela-tarantula/jsonpatchx/python-tests.yml?branch=main&label=Tests&style=flat)](https://github.com/angela-tarantula/jsonpatchx/actions)
[![Codecov](https://codecov.io/github/angela-tarantula/jsonpatchx/graph/badge.svg)](https://codecov.io/github/angela-tarantula/jsonpatchx)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/angela-tarantula/jsonpatchx/badge)](https://scorecard.dev/viewer/?uri=github.com/angela-tarantula/jsonpatchx)
[![Contributor Covenant](https://img.shields.io/badge/Contributor%20Covenant-3.0-fbab2c.svg)](CODE_OF_CONDUCT.md)

<!-- markdownlint-enable MD013 -->

## About The Project

[RFC 6902](https://datatracker.ietf.org/doc/html/rfc6902) (JSON Patch) is
intentionally minimal and transport-focused. That's great for interoperability,
but modern PATCH traffic crosses trust boundaries: browser clients, internal
services, third-party integrations, and increasingly LLM-generated patch
payloads.

### JsonPatchX supports standard JSON Patch and adds a contract layer

- **Input Safety**: Patch operations are Pydantic models, so malformed payloads
  fail fast with clear, structured errors.

- **FastAPI Native**: Set up PATCH routes quickly with minimal boilerplate.

### It also provides extensibility beyond the RFC

- **Richer Operations**: Define custom patch operations such as `increment`,
  `toggle`, or `replace_substring` so updates express intent directly instead of
  relying on brittle sequences of low-level steps.

- **Typed targeting**: pointers participate in typed contracts, with clear
  failure modes when a resolved path has the wrong shape or type.

- **Expressive targeting**: use standard
  [JSON Pointer](https://datatracker.ietf.org/doc/html/rfc6901), the new
  [RFC 9535](https://datatracker.ietf.org/doc/html/rfc9535) JSONPath, or your
  own custom resolver.

### And it treats the patch layer as a first-class contract

- **Live Contract Sync**: OpenAPI is generated from the same runtime patch
  models, so documentation stays aligned automatically.

- **Surface Control**: Operations can be allow-listed per route to limit what
  clients can do.

- **Lifecycle Management**: Evolve operation contracts over time with additive
  schema changes and deprecations.

## Getting Started

### Installation

```sh
pip install jsonpatchx
```

### Usage

#### 1. Standard RFC 6902

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

#### 2. The FastAPI Contract

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

> **Note**: For custom operations, JSONPath targeting, and advanced FastAPI
> route helpers, see the
> [Full Documentation](https://angela-tarantula.github.io/jsonpatchx/).

## Join the Experiment

JsonPatchX is a playground for the future of JSON Patch. With the recent
standardization of JSONPath, we are exploring more expressive ways to handle
mutations.

- **Discuss**: Join the project
  [Discussions](https://github.com/angela-tarantula/jsonpatchx/discussions) or
  the broader [json-patch2](https://github.com/json-patch/json-patch2) forum.
- **Contribute**: See
  [CONTRIBUTING.md](https://www.google.com/search?q=CONTRIBUTING.md) to help
  shape the roadmap. Any contributions you make are **greatly appreciated**. See
  the [open issues](https://github.com/angela-tarantula/jsonpatchx/issues) for a
  list of proposed features (and known issues).

## License & Contact

Distributed under the MIT License. Created by Angela Liss
([chamsester@gmail.com](mailto:chamsester@gmail.com)).

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
