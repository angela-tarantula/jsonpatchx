# jsonpatchx

**PATCH is an API contract, not just a transport format.** A framework for
**governed, type-safe, and versionable** partial updates in Python.

<!-- markdownlint-disable MD013 -->

[![Release](https://img.shields.io/github/v/release/angela-tarantula/json-patch-x?display_name=tag)](CHANGELOG.md)
[![Tests](https://img.shields.io/github/actions/workflow/status/angela-tarantula/json-patch-x/python-app.yml?branch=main&label=CI&style=flat)](https://github.com/angela-tarantula/json-patch-x/actions)
![RFC 6902 compatible core](https://img.shields.io/badge/RFC-6902-blue)
![FastAPI ready](https://img.shields.io/badge/FastAPI-First%20Class-009688)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/angela-tarantula/json-patch-x/badge)](https://scorecard.dev/viewer/?uri=github.com/angela-tarantula/json-patch-x)
[![Contributor Covenant](https://img.shields.io/badge/Contributor%20Covenant-3.0-fbab2c.svg)](CODE_OF_CONDUCT.md)

<!-- markdownlint-enable MD013 -->

## About The Project

`jsonpatchx` is a Python framework for governed partial updates using JSON Patch
(RFC 6902).

It is designed for teams that want PATCH behavior to be explicit, typed, and
documented, not just loosely validated request payloads.

In practice, it gives you:

- RFC 6902-compatible core operations (`add`, `remove`, `replace`, etc.)
- Pydantic-backed validation for operations and target value types
- Extensible operation registries for domain-specific patch operations
- FastAPI integration that keeps request enforcement and OpenAPI docs aligned

## Getting Started

Install from PyPI:

### Installation

```sh
pip install jsonpatchx
```

## Usage

Basic patch application:

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

For practical end-to-end examples:

- FastAPI demos: [examples/fastapi/README.md](examples/fastapi/README.md)
- Operation recipes: [examples/recipes.py](examples/recipes.py)
- Error payload shapes: [docs/demo-error-shapes.md](docs/demo-error-shapes.md)

## Roadmap

See the [open issues](https://github.com/angela-tarantula/json-patch-x/issues)
for a list of proposed features (and known issues).

## Contributing

Contributions are what make the open source community such an amazing place to
learn, inspire, and create. Any contributions you make are **greatly
appreciated**. For detailed contributing guidelines, please see
[CONTRIBUTING.md](CONTRIBUTING.md)

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for more information.

## Contact

Anglea Liss - [chamsester@gmail.com](mailto:chamsester@gmail.com)

Project Link:
[https://github.com/angela-tarantula/json-patch-x](https://github.com/angela-tarantula/json-patch-x)

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
