# Local Docs Preview

JsonPatchX already has a documented local workflow for docs work. Use that
workflow instead of improvising separate commands.

## Preview the docs locally

```sh
python -m pip install --upgrade pip uv
git clone https://github.com/angela-tarantula/jsonpatchx
cd jsonpatchx
git submodule update --init
uv sync
uv run zensical serve
```

That starts the local preview server.

To build the site without serving it:

```sh
uv run zensical build
```

## What to edit when docs move around

The navigation order lives in `zensical.toml`.

That file should reflect the actual learning sequence of the site, not just a
list of available pages. When you add or split a page, check whether the
surrounding pages still tell a sensible story in the left nav.

## Docs review checklist

Before opening a docs PR, check four things:

- a first-time reader can understand why the page exists
- examples match the current public API, not an older draft
- page titles describe decisions or concepts, not only implementation details
- the change belongs in User Guide, Developer Reference, or API Reference for a
  clear reason

## What usually causes drift

Docs drift most often when code examples, OpenAPI behavior, and generated API
pages are updated on different schedules.

The safest pattern is:

1. change the code;
2. update the user-facing example that demonstrates it;
3. regenerate or review the matching API Reference page;
4. snapshot any OpenAPI or error-contract changes in tests.

That keeps the narrative docs and the runtime contract moving together.
