# AGENTS.md

## Documentation Structure

Before rewriting or compacting docs, inspect the heading outline as both a human
and an MCP would.

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
- Dignify the reader's intelligence. Do not explain reasonably self-obvious
  behavior or benefits at unnecessary length.
