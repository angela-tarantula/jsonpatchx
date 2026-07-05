# Documentation Standards for `docs/`

Apply these standards when creating or editing any Markdown page under `docs/`.
These pages are the source for the published site at
<https://angela-tarantula.github.io/jsonpatchx/>, built with Zensical
(`zensical.toml`).

Every page must support four goals:

- Discoverability: readers can scan a page and navigate to what they need
  quickly.
- Actionability: readers can complete real tasks accurately, safely, and
  confidently.
- Retrievability: search engines and AI agents can identify the most relevant
  page or section for a query.
- Self-contained excerpts: any excerpt or retrieved passage remains
  understandable on its own, without unstated background information.

## Working Process

### Before Editing

1. Identify the reader, the task, the scope, and the success condition.
2. Find the canonical source for every fact, command, API, setting,
   compatibility, version, and behavior claim: `jsonpatchx/` for code behavior,
   `tests/` for verified behavior, `pyproject.toml` for dependencies and extras,
   and the governing specification or upstream documentation when the claim
   depends on an external standard.
3. Check whether related pages already exist. Link to the canonical page instead
   of duplicating its content.
4. Ask for missing information only when it cannot be inferred safely from the
   repository.

### While Editing

1. Put the most useful task information before background explanation.
2. For task, reference, and troubleshooting pages, begin with a concise
   statement of the page's scope, intended reader when relevant, and expected
   result before expanding into background or procedure.
3. Make implicit requirements, relationships, assumptions, and consequences
   explicit.
4. Convert dense prose into headings, steps, bullets, tables, examples, or
   callouts when structure carries meaning.
5. Keep changes scoped to the request unless broader edits are required for
   correctness.

### Before Finishing

1. Review headings, terminology, links, examples, warnings, and Markdown
   semantics.
2. Preview rendering with the docs preview workflow described in
   `CONTRIBUTING.md` whenever layout, callouts, or diagrams changed.
3. Flag unverified facts, placeholders, and open questions for human review.
4. Summarize what changed, where it changed, how it was checked, and what
   remains uncertain.

## Core Principles

- Be specific: name exact products, commands, files, classes, exceptions,
  states, and outcomes.
- Be explicit: state requirements, prerequisites, relationships, constraints,
  and assumptions.
- Use examples: include commands, sample input, sample output, syntax, and
  realistic scenarios.
- Be consistent: use predictable structure, terminology, formatting, and link
  patterns, and match the conventions of neighboring pages.
- Preserve meaning in source: use Markdown for semantic structure, not visual
  appearance.

## Functional Headings

Write headings that work as search results, table-of-contents entries, and
retrieval anchors.

Do:

- Use literal, specific, accurate, concise heading text that contains the
  keywords a reader would search for.
- Use one H1 per page, and use heading levels that reflect hierarchy. Do not
  skip levels.
- Write at least one sentence of prose under a heading before the next heading
  begins; never stack headings back to back.
- Split a large mixed-focus section into separate pages when it covers more than
  one task.
- Use the words readers are likely to search for in the page title or H1,
  headings, link text, and opening summary.

Avoid:

- Figurative headings such as `Opening the Toolbox`.
- Vague headings such as `More Details`.
- Misleading headings such as `Getting Started` on a page that only covers
  installing the `fastapi` extra.
- Verbose headings, bold text posing as a heading, and headings used only for
  emphasis.

Example rewrites:

- `Want to help push this forward?` →
  `Drafting a PEP for Recursive Generic Constraints`
- `Now Is the Time to Experiment` → `Contributing New Operation Patterns`
- `More Details` → `Backend Type-Gating Failure Modes`
- `How to Register a New Custom JSON Patch Operation with a FastAPI PATCH Route`
  → `Registering a Custom Operation with FastAPI`

## Clear Meaning and Explicit Language

Do not make readers or AI agents infer important details.

Prefer:

- Exact entity names over pronouns.
- Concrete terms over broad references.
- Complete cause-and-effect statements.
- Specific file types, commands, flags, outputs, error codes, and status names.
- Project-specific names alongside established terms on first use:
  `JSONPointer, an RFC 6901 JSON Pointer`.
- Alternative names alongside internal terms:
  `JSONBound, the TypeVar bound for JSON-shaped values`.

Example rewrites:

- `Raises RFC-compliant exceptions.` → `RemoveOp.apply()` raises
  `PatchConflictError` if the target is missing or is the document root (because
  PATCH cannot delete the document).
- `The document is copied first for safety.` →
  `apply(doc, inplace=False) deep-copies doc first, so the original is never mutated.`
- `Non-literal ops will not work.` → A missing `op: Literal[...]` annotation
  raises `InvalidOperationDefinition` at class-definition time.
- `Path fields also show what type they point to.` → Every `JSONPointer[T]`
  field's `path` property is typed as a string, but its `x-pointer-type-schema`
  shows the schema of `T`; for `JSONPointer[JSONBoolean]`, that is
  `{"type": "boolean"}`.

## Examples, Commands, and Outputs

Use examples whenever syntax, order, results, or interpretation could be
unclear.

For commands and code samples:

- Put commands, code, configuration, logs, and templates in fenced code blocks
  with language tags.
- Introduce each command with the scenario, directory, prerequisite, or expected
  effect.
- Prefer exact commands over generic descriptions.
- Show a full, runnable example instead of a partial snippet or a "see the API
  reference" pointer, and verify it against `jsonpatchx/` or `tests/` before
  publishing.
- Demonstrate a format directly instead of only naming it.
- Use an example to illustrate an abstract rule; do not restate the rule in
  different words.
- Explain destructive or irreversible effects before the command that causes
  them.
- Use correct, idiomatic, maintainable sample code; add comments only for
  non-obvious behavior.

Example rewrites:

- `Send a JSON Patch document.` → Show a sample `application/json-patch+json`
  request body.
- `Run the tests to make sure it works.` →
  `Run uv run pytest -m integration, or uv run pytest -v for everything.`
- `The fuzzer reports a failure.` → When it finds a crash, libFuzzer writes a
  reproducer file like `/tmp/jsonpatchx_artifacts/crash-<hash>` that you can
  replay directly:
  `uv run --python 3.13 python -m fuzzers.jsonpatchx_fuzzer crash-<hash>`.

## Semantic Markdown Rules

Use Markdown elements for document purpose, not visual styling.

### Headings

- Use headings only for page section structure.
- Do not use heading levels to control font size or to emphasize warnings.

### Emphasis

- Use bold or italic only for a phrase or sentence that needs emphasis.

### Blockquotes and Callouts

- Use a blockquote, or the callout syntax already used on neighboring pages, for
  important prose blocks. Confirm rendering with the docs preview before
  introducing a new callout style.
- State the consequence in the callout title or first sentence.
- Do not hide critical warnings in collapsed callouts or details blocks.

Example rewrite:

- `## ⚠️ Never Delete the Root` →
  `> **Warning:** RemoveOp.apply() raises PatchConflictError on the document root.`

### Code Blocks

- Use fenced code blocks only for code, commands, logs, templates,
  configuration, or preformatted copyable text.
- Do not put prose checklists or ordinary text inside code fences for visual
  boxing.

### Lists and Tables

- Use numbered lists for sequenced steps, ranked items, and procedures where
  order matters.
- Use bullet lists for related items where order does not matter.
- Use nested lists to show hierarchy or grouping; do not flatten related
  sub-items (such as an op's fields) into one list.
- Do not write steps or list items as dense prose.
- Use tables when each item has multiple comparable attributes; use bullets when
  each item has one main description.

## Accessibility and Source-Only Content

Make essential information available in text and in source markup.

Do:

- Keep critical warnings, prerequisites, and constraints visible in normal page
  text.
- Add descriptive alt text to every meaningful image.
- Put essential process steps, labels, and decisions in text, not only in
  images.
- Prefer Mermaid or other text-based diagrams when relationships must be
  searchable or maintainable.
- Use details blocks only for optional background or secondary explanation.

Avoid:

- Images that contain the only copy of important instructions.
- Decorative emoji in headings or in important guidance.
- Collapsed warnings whose visible text hides the consequence.
- Visual-only cues that disappear in source, search, screen readers, or AI
  retrieval.

Example: an architecture diagram with no alt text, as the only explanation of
the module layering →
`alt="types.py feeds backend.py, schema.py, builtins.py, registry.py"`, plus the
same layering restated in page text.

## Links and Related Information

Use links to state explicit relationships between pages.

Do:

- Link to the canonical page instead of duplicating its content.
- Use descriptive link text that matches the target topic or heading.
- Embed links in sentences that explain what the reader will find.
- Update or remove links when pages move, become outdated, or are superseded.
- Remember that heading text generates the URL anchor: before renaming a
  heading, search `docs/` for links to the old anchor and update them.

Avoid:

- Link text like `click here`, `this page`, or a bare URL.
- Standalone links with no explanatory context.
- Copying volatile details from another page when a link is safer.

Example rewrites:

- `More on errors here.` →
  `PatchConflictError's HTTP mapping is documented in Error Semantics.`
- `See the docs for how validation works.` →
  `See Evolving PATCH Contracts for how field additions and removals affect validation.`

## HTML Comments for Editors and AI Agents

Markdown comments (`<!-- ... -->`) never render on the published site but remain
available in the Markdown source for maintainers and source-aware tooling.

Use comments only for editor-facing maintenance notes, such as pointers to a
source of truth or invariants that edits must preserve:

```markdown
<!-- This table mirrors _patch_error_response_map in jsonpatchx/fastapi.py.
     Update both together. -->
```

Rules:

- Never put reader-essential content (warnings, prerequisites, constraints,
  steps) only in a comment; it is invisible on the rendered site.
- Keep each comment short, factual, and current; delete it once the note it
  carries is no longer true.
- A comment must never contradict the visible page text. When they conflict, the
  visible text wins, and the comment must be fixed or removed.

## Documentation Ecosystem Hygiene

Prevent outdated pages from misleading readers or AI agents.

- If a page describes a removed API, delete the page or mark it clearly
  historical and link to its replacement. For example, do not leave a page
  describing `PatchInputError` as current after it is removed from `__all__`.
- Keep maintainer-only process notes out of user-facing guides; they belong in
  `CONTRIBUTING.md`, not in `docs/user-guide/`.
- If content changes frequently, link to the source of truth instead of copying
  volatile details.

## Required Validation

A docs change is not done until both checks below pass.

1. Build the docs with `uv run zensical build --clean` so a broken link, bad
   front matter, or malformed page is caught before merging.
   `uv run zensical serve` is fine for iterative preview, but it has no
   `--clean` flag, so run `build --clean` as the actual gate.
2. Lint the change: run `uv run prek run --files <the files you touched>`
   instead of `uv run prek run --all-files`.

## AI Editing Boundaries

You may help with summaries, clearer headings, explicit rewrites, parallel
structure, concise edits, undefined terms, example suggestions, alt text drafts,
and review checklists.

Do not assume:

- What readers already know.
- What is outside the page or project scope.
- Which page is canonical when sources conflict.
- That generated Markdown is semantically correct without review.
- That examples, commands, or API behavior are correct without source
  verification.

When facts are uncertain:

- Say what needs verification.
- Mark placeholders clearly.
- Do not invent commands, flags, filenames, configuration keys, or behavior;
  check `jsonpatchx/` or `tests/` before writing a claim about behavior.
- Prefer a short question over a confident, unsupported claim.
