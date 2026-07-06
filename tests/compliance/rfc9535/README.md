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

## Without `jsonpatchx[strict-jsonpath]`

`python-jsonpath[strict]` is an opt-in extra, installed via
`jsonpatchx[strict-jsonpath]`, not a default dependency. Its upstream
[`iregexp-check`](https://github.com/jg-rp/rust-iregexp) dependency segfaults on
import under free-threaded Python, and PEP 508 dependency markers cannot select
a standard build over a free-threaded build of the same Python version, so
JsonPatchX cannot install it automatically only on safe interpreters; installing
it is left to the caller. See
[Targeting Documents with JSON Pointer and JSONPath](../../../docs/user-guide/patch-targeting.md)
for the install command and the free-threading warning.

`test_selector.py` detects whether `iregexp-check` is actually importable in the
current environment (not the Python version) and xfails a small, hand-picked set
of regular expression compliance cases when it is missing: without it, the
built-in backend falls back to Python's built-in `re` engine instead of the full
RFC/I-Regexp path.

The manifest is intentionally narrow and strict: only empirically failing cases
are listed, so an unexpected pass becomes an `XPASS`.

## Running Tests Locally

If [`external`](./external/) is empty, initialize the submodule first:

```bash
git submodule update --init --recursive
```

Then run the compliance tests normally. To exercise the full RFC 9535 path (not
just the `re`-fallback behavior), install `strict-jsonpath` first, and only do
so on a standard (non-free-threaded) interpreter:

```bash
uv sync --extra strict-jsonpath
uv run pytest tests/compliance/rfc9535/test_selector.py
```

Without the extra, the same command still runs, but the cases listed in
`test_selector.py` are expected to xfail instead of pass:

```bash
uv sync
uv run pytest tests/compliance/rfc9535/test_selector.py
```
