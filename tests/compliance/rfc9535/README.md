# RFC 9535 Compliance Test Data

This directory runs the official JSONPath Compliance Test Suite against
JsonPatchX's built-in `JSONSelector` backend.

## Test Data Layout

- [`external`](./external/): a
  [Git submodule](https://git-scm.com/book/en/v2/Git-Tools-Submodules) of the
  official JSONPath compliance suite.
- [`case_loader.py`](./case_loader.py): loads raw `cts.json` records and splits
  them into valid-selector and invalid-selector cases.
- [`test_selector.py`](./test_selector.py): executes the suite through
  `JSONSelector.parse(...).getall(...)`.

## Python 3.14 and Later

On Python 3.14 and later, the built-in backend xfails a small set of regular
expression compliance cases.

This is due to an upstream compatibility gap in
[`python-jsonpath`](https://github.com/jg-rp/python-jsonpath) /
[`iregexp-check`](https://github.com/jg-rp/rust-iregexp), so JsonPatchX falls
back to Python's built-in `re` engine instead of the full RFC/I-Regexp path.

The manifest is intentionally narrow and strict: only empirically failing cases
are listed, so an unexpected pass becomes an `XPASS`.

## Running Tests Locally

If [`external`](./external/) is empty, initialize the submodule first:

```bash
git submodule update --init --recursive
```

Then run the compliance tests normally:

```bash
uv sync
uv run pytest tests/compliance/rfc9535/test_selector.py
```
