# Getting Started

This guide gets you to a first successful patch quickly.

## Install

Core library:

```sh
pip install jsonpatchx
```

FastAPI route helpers:

```sh
pip install "jsonpatchx[fastapi]"
```

`JsonPatchFor` is part of core. The extra adds helpers in `jsonpatchx.fastapi`
(for example `JsonPatchRoute` and error mapping).

## First Patch (Plain JSON)

```python
from jsonpatchx import apply_patch

doc = {"name": "Ada", "roles": ["engineer"]}
patch = [
    {"op": "replace", "path": "/name", "value": "Ada Lovelace"},
    {"op": "add", "path": "/roles/-", "value": "maintainer"},
]

updated = apply_patch(doc, patch)
```

`apply_patch(...)` deep-copies by default, so `doc` is unchanged unless you use
`inplace=True`.

## Parse Once, Apply Many

```python
from jsonpatchx import JsonPatch

patch = JsonPatch(
    [
        {"op": "replace", "path": "/name", "value": "Ada Lovelace"},
        {"op": "add", "path": "/roles/-", "value": "maintainer"},
    ]
)

updated = patch.apply({"name": "Ada", "roles": ["engineer"]})
```

Use `JsonPatch` when you want to validate once and reuse the same patch object.
