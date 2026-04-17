# Contributing

Thank you for being interested in contributing to JsonPatchX. There are many
ways to contribute to the project:

- try JsonPatchX and report bugs or rough edges
- implement new features or fixes
- review pull requests
- improve documentation and examples
- participate in design discussions

Please keep all project interaction within the
[Code of Conduct](/CODE_OF_CONDUCT.md).

## Reporting Bugs or Other Issues

Contributions should usually start with a discussion.

Use [Discussions](https://github.com/angela-tarantula/jsonpatchx/discussions)
for design questions, feature ideas, and uncertain bug reports. Use
[Issues](https://github.com/angela-tarantula/jsonpatchx/issues) for concrete,
actionable bugs or scoped work once the problem is clear.

When reporting a bug, include as much of the following as you can:

- OS platform
- Python version
- installed dependency versions, for example `uv tree` or `python -m pip freeze`
- a minimal code sample
- the traceback or failing output
- expected behavior and actual behavior

You should always try to reduce examples to the smallest case that still shows
the problem.

If you discover a security bug, do not report it through GitHub. See
[SECURITY.md](/SECURITY.md).

## Development

Install
[uv](https://docs.astral.sh/uv/getting-started/installation/#installing-uv):

```sh
python -m pip install --upgrade pip uv
```

Clone the repository and install dependencies:

```sh
git clone https://github.com/angela-tarantula/jsonpatchx
cd jsonpatchx
git submodule update --init
uv sync
```

Install [prek](https://github.com/j178/prek):

```sh
uv tool install prek
prek install
```

> See the [Prek quick reference](#prek-quick-reference) below for common local
> hook commands.

## Testing and Linting

Run the test suite with:

```sh
uv run pytest -v
uv run --managed-python -p 3.12 pytest
```

Run type checks with:

```sh
uv run mypy .
```

Run formatting with:

```sh
uv run ruff format
```

To run the full local hook set, use:

```sh
prek run --all-files
```

## Documenting

Documentation pages live under `docs/`. Site navigation and page order live in
`zensical.toml`.

Preview the docs locally with:

```sh
uv run zensical serve
```

Build the docs with:

```sh
uv run zensical build
```

## Pull Requests

Before opening a pull request, check whether the change has already been
discussed in Discussions, Issues, or another open PR.

Pull requests should include tests for affected behavior. If a change affects
the public API or documented behavior, update the relevant docs or examples in
the same PR.

## Prek quick reference

- Run all configured hooks manually:

  ```sh
  prek run --all-files
  ```

- List available hook IDs:

  ```sh
  prek list
  ```

- Run one specific hook:

  ```sh
  prek run checkov --all-files
  ```

- Skip one hook for one commit:

  ```sh
  PREK_SKIP=checkov git commit -m "message"
  ```

- Skip multiple hooks for one commit:

  ```sh
  PREK_SKIP=checkov,openapi git commit -m "message"
  ```

- Skip all hooks for one commit:

  ```sh
  git commit --no-verify -m "message"
  ```

CI still runs required checks on pushes and pull requests, so skipping local
hooks does not bypass CI requirements.
