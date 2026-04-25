# AGENTS.md

## Documentation Structure

Before rewriting or compacting docs, inspect the heading outline as both a human
and a Model Context Protocol (MCP) client would.

- Dignify the reader's intelligence. Do not explain reasonably self-obvious
  behavior or benefits at unnecessary length.
- Do not create umbrella headings unless they group at least two real peer
  subsections and have a short intro paragraph.
- If a heading names `X` and `Y`, then `X` and `Y` must both appear as peer
  topics in the outline.
- Every heading must describe the content directly under it.
- Do not begin a heading with inline code. If a symbol or type name appears in
  the heading, phrase it so the heading still reads naturally in prose.
- Use noun-phrase headings for conceptual sections.
- Use action/task headings for procedural sections.
- Introduce concepts from their actual guarantees and boundaries: say what is
  parsed up front, what is enforced later, what is validated where, and what a
  type or abstraction does and does not promise.
- Take extra care when adding, removing, or moving sections so that concepts are
  introduced before later sections rely on them.
- Avoid lookahead prose such as "later on this page..."
- Optimize for semantic hierarchy, scanability, and machine-readable structure.

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
