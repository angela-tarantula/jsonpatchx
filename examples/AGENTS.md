# Examples Agent Guide

The instructions for writing a JsonPatchX custom operation live at
[`docs/custom-operation-agent-guide.md`](../docs/custom-operation-agent-guide.md).
Read that guide before writing or editing an operation in this directory. This
file is a pointer plus rules local to this directory; it must stay a pointer and
never become a second copy of the guide.

## Rules Local to This Directory

- Keep every example runnable, complete Python, not pseudocode.
- Follow the existing layout: reusable operations belong in
  [`recipes.py`](recipes.py) or [`recipes2.py`](recipes2.py), and
  [`fastapi/`](fastapi/) demo files show how operations are assembled into
  registries and routes, not where new operation catalogs go.
- If you add or change runnable example behavior, prefer targeted checks over
  broad repo-wide validation.
