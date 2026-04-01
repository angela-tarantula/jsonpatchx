# JsonPatchX

<!-- markdownlint-disable MD013 -->

[![Tests](https://img.shields.io/github/actions/workflow/status/angela-tarantula/jsonpatchx/python-tests.yml?branch=main&label=Tests&style=flat)](https://github.com/angela-tarantula/jsonpatchx/actions)
[![Codecov](https://codecov.io/github/angela-tarantula/jsonpatchx/graph/badge.svg)](https://codecov.io/github/angela-tarantula/jsonpatchx)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/angela-tarantula/jsonpatchx/badge)](https://scorecard.dev/viewer/?uri=github.com/angela-tarantula/jsonpatchx)
[![Contributor Covenant](https://img.shields.io/badge/Contributor%20Covenant-3.0-fbab2c.svg)](CODE_OF_CONDUCT.md)

<!-- markdownlint-enable MD013 -->

## About The Project

JsonPatchX is a typed JSON Patch toolkit for building governed PATCH APIs in
Python.

It scales from simple patching to highly controlled API contracts:

- Plain JSON patching
- FastAPI PATCH endpoints
- Expressive, governed PATCH APIs with typed pointers, custom operations, route
  allow-lists, JSONPath pointers, and more.

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

- FastAPI demos: [examples/README.md](examples/README.md)
- Operation recipes: [examples/recipes.py](examples/recipes.py)
- Error payload shapes: [docs/demo-error-shapes.md](docs/demo-error-shapes.md)

## Roadmap

See the [open issues](https://github.com/angela-tarantula/jsonpatchx/issues) for
a list of proposed features (and known issues).

## Contributing

Contributions are what make the open source community such an amazing place to
learn, inspire, and create. Any contributions you make are **greatly
appreciated**. For detailed contributing guidelines, please see
[CONTRIBUTING.md](CONTRIBUTING.md)

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
