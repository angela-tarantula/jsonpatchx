# RFC 6902 Compliance Test Data

This directory organizes tests into 3 places:

- [`external`](./external/): a
  [Git submodule](https://git-scm.com/book/en/v2/Git-Tools-Submodules) of
  external RFC6902 compliance tests
- [`jsonpatchx_test.json`](./jsonpatchx_tests.json): additional JSON coverage to
  cover behaviors we considered underrepresented in upstream fixtures while
  still running upstream compatibility tests unchanged.
- [`jsonpatchx_nonfinite_tests.json`](./jsonpatchx_nonfinite_tests.json):
  non-finite number cases (`NaN`, `Infinity`, `-Infinity`) used to validate
  JSON/Python edge behavior.

## Running Tests Locally

If you find that [`external`](./external/) is empty (which will fail tests),
simply initialize the submodule:

```bash
git submodule update --init --recursive
```

Then you can run tests normally:

```bash
uv sync
uv run pytest
```

## Known Upstream Fixture Bug

One upstream record with comment `"Whole document"` is missing an `"expected"`
field.

In [`test_patch.py`](./test_patch.py), we patch this case at load time by
setting:

- `expected = doc`

Why this is correct:

- The operation is a `test` against path `""` (whole document), and `test` is an
  assertion operation, not a mutating one.
- So the post-apply document should remain identical to the input document.

This keeps upstream source data untouched while making the test record
executable.
