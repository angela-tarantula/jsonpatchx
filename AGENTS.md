# AGENTS.md

## Docstring Style

When editing public Python docstrings, match the repo's Google-style section
labels and the way Zensical renders them.

- Prefer explicit section labels such as `Arguments`, `Returns`, `Raises`,
  `Examples`, and `Notes` when they add real structure.
- Use `Notes` for guarantees, caveats, invariants, and explanatory prose that
  should render as a distinct block.
- Use `Examples` when a concrete example materially helps an API reader; do not
  add placeholder examples just to fill the section.
- Keep the opening sentence concrete and descriptive, then use sections for the
  rest.
- Before writing a docstring, check whether the function/class is public (no
  leading underscore, reachable from `jsonpatchx/__init__.py` or otherwise part
  of the documented surface) or private. Public docstrings are read by callers
  who never see the implementation; private docstrings are read by maintainers
  who already have it open. Write for that actual reader: a public docstring
  states the contract (inputs, outputs, guarantees, what to catch); it does not
  explain why the implementation isn't shaped some other way, why a related type
  isn't used instead, or other design-decision rationale aimed at a future
  maintainer. That belongs in a code comment, the PR description, or
  `CHANGELOG.md`, not in text a caller has to read past to learn how to use the
  thing. Private docstrings have more room for implementation reasoning, but
  should still not sit as design manifestos if the actual contract is not the
  code's own point.

## Changelog Writing

Write `CHANGELOG.md` entries from the perspective of supported public API and
observable user-facing behavior.

- Changelogs are for humans. Optimize for what a reader can understand and rely
  on, not for exhaustive implementation detail.
- Preserve the existing Keep a Changelog structure: newest version first, dated
  releases, and stable section headings under each version.
- Keep an entry for every version; do not skip releases in the history.
- Group like changes under the same section instead of scattering them through
  ad hoc bullets.
- Preserve linkable version and section headings.
- Preserve the existing note that the project follows Semantic Versioning.
- Do not log internal helper removals, refactors, rewiring, or implementation
  cleanup unless they changed supported public behavior.
- Use the standard section types when they fit: `Added`, `Changed`,
  `Deprecated`, `Removed`, `Fixed`, and `Security`.
- Treat those section labels as public-API and user-visible-behavior categories,
  not as a ledger of internal code motion.
- Use `Added` for new public API surface, newly documented support, and new
  user-visible capabilities.
- Use `Changed` only when an existing supported public API or documented
  behavior changed.
- If a symbol or behavior was technically reachable before but is now being
  explicitly acknowledged and supported as public API, treat that as `Added`.
- Keep entries focused on what users can now rely on, not on the internal
  mechanism used to implement it.

## Testing the Examples Agent Guide

Use a prompt-only subagent check when you need to evaluate
[`examples/AGENTS.md`](examples/AGENTS.md).

See [`tests/agents/README.md`](tests/agents/README.md) for the reproducible
procedure, fixture prompts, and evaluation rubric.

### Run the Harness Deliberately

- Use `fork_context:false` so the child agent does not inherit this thread.
- Inline the contents of [`examples/AGENTS.md`](examples/AGENTS.md) and exactly
  one fixture from [`tests/agents/`](tests/agents/).
- Tell the child agent to use only the pasted instruction text and prompt, and
  to return only Python code.
- When reporting the check, include the generated Python for each fixture so the
  reviewer can judge the result directly.

### Do Not Overclaim the Result

- This prompt-only harness shows whether the child agent can produce a good
  answer from the inline guidance.
- It does not by itself prove that the child agent was unable to inspect other
  workspace files.
- If that stronger claim matters, audit the child tool usage or run the check in
  a more isolated environment.
