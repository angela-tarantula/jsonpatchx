"""
Minimal JSON Pointer helpers (baseline).

Known bugs / gaps (intentional):
- No full RFC 6901 validation or escaping coverage.
- Swap does not prevent parent/child relationships.
- Array add semantics are incomplete (insert vs replace differences).
- Root removal semantics differ from RFC 6902.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException


def _tokens(ptr: str) -> list[str]:
    if ptr == "":
        return []
    if not ptr.startswith("/"):
        raise HTTPException(status_code=400, detail=f"Invalid JSON Pointer: {ptr!r}")
    tokens = ptr.split("/")[1:]
    return [t.replace("~1", "/").replace("~0", "~") for t in tokens]


def get_value(doc: Any, ptr: str) -> Any:
    cur = doc
    for tok in _tokens(ptr):
        if isinstance(cur, dict):
            if tok not in cur:
                raise HTTPException(status_code=400, detail=f"Path not found: {ptr!r}")
            cur = cur[tok]
        elif isinstance(cur, list):
            if tok == "-" or not tok.isdigit():
                raise HTTPException(
                    status_code=400, detail=f"Invalid array index in {ptr!r}"
                )
            i = int(tok)
            if i < 0 or i >= len(cur):
                raise HTTPException(
                    status_code=400, detail=f"Index out of range in {ptr!r}"
                )
            cur = cur[i]
        else:
            raise HTTPException(status_code=400, detail=f"Non-container at {ptr!r}")
    return cur


def set_value(doc: Any, ptr: str, value: Any) -> Any:
    toks = _tokens(ptr)
    if not toks:
        return value

    cur = doc
    for tok in toks[:-1]:
        if isinstance(cur, dict):
            if tok not in cur:
                raise HTTPException(status_code=400, detail=f"Path not found: {ptr!r}")
            cur = cur[tok]
        elif isinstance(cur, list):
            if tok == "-" or not tok.isdigit():
                raise HTTPException(
                    status_code=400, detail=f"Invalid array index in {ptr!r}"
                )
            i = int(tok)
            if i < 0 or i >= len(cur):
                raise HTTPException(
                    status_code=400, detail=f"Index out of range in {ptr!r}"
                )
            cur = cur[i]
        else:
            raise HTTPException(status_code=400, detail=f"Non-container at {ptr!r}")

    last = toks[-1]
    if isinstance(cur, dict):
        cur[last] = value
        return doc
    if isinstance(cur, list):
        if last == "-":
            cur.append(value)
            return doc
        if not last.isdigit():
            raise HTTPException(
                status_code=400, detail=f"Invalid array index in {ptr!r}"
            )
        i = int(last)
        if i < 0 or i > len(cur):
            raise HTTPException(
                status_code=400, detail=f"Index out of range in {ptr!r}"
            )
        if i == len(cur):
            cur.append(value)
        else:
            cur[i] = value
        return doc

    raise HTTPException(status_code=400, detail=f"Non-container at {ptr!r}")
