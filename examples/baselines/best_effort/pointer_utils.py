"""
Best-effort JSON Pointer helpers (still incomplete).

Limitations (intentional):
- Pattern is simplistic and does not handle all RFC 6901 edge cases.
- Array index parsing is minimal.
- Missing parent containers are not created.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from pydantic import StringConstraints
from typing_extensions import Annotated

POINTER_PATTERN = r"^(?:/(?:[^~/]|~[01])*)*$"
JsonPointerStr = Annotated[str, StringConstraints(pattern=POINTER_PATTERN)]


def resolve_pointer(doc: Any, ptr: str) -> Any:
    if ptr == "":
        return doc
    if not ptr.startswith("/"):
        raise HTTPException(status_code=400, detail=f"Invalid JSON Pointer: {ptr!r}")
    tokens = [t.replace("~1", "/").replace("~0", "~") for t in ptr.split("/")[1:]]
    cur = doc
    for tok in tokens:
        if isinstance(cur, dict):
            cur = cur[tok]
        elif isinstance(cur, list):
            if not tok.isdigit():
                raise HTTPException(status_code=400, detail="Invalid list index")
            cur = cur[int(tok)]
        else:
            raise HTTPException(status_code=400, detail="Non-container")
    return cur


def set_pointer(doc: Any, ptr: str, value: Any) -> Any:
    if ptr == "":
        return value
    if not ptr.startswith("/"):
        raise HTTPException(status_code=400, detail=f"Invalid JSON Pointer: {ptr!r}")
    tokens = [t.replace("~1", "/").replace("~0", "~") for t in ptr.split("/")[1:]]
    cur = doc
    for tok in tokens[:-1]:
        if isinstance(cur, dict):
            cur = cur[tok]
        elif isinstance(cur, list):
            if not tok.isdigit():
                raise HTTPException(status_code=400, detail="Invalid list index")
            cur = cur[int(tok)]
        else:
            raise HTTPException(status_code=400, detail="Non-container")
    last = tokens[-1]
    if isinstance(cur, dict):
        cur[last] = value
        return doc
    if isinstance(cur, list):
        if not last.isdigit():
            raise HTTPException(status_code=400, detail="Invalid list index")
        cur[int(last)] = value
        return doc
    raise HTTPException(status_code=400, detail="Non-container")
