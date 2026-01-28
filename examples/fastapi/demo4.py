"""
Demo 4: spellbook dot-runes pointer backend with FastAPI dependency injection.
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import Depends, HTTPException, Path

from examples.fastapi.shared import (
    AppendOp,
    Apprentice,
    ApprenticeId,
    IncrementOp,
    RunePointer,
    SpellbookId,
    create_app,
    get_apprentice,
    get_spellbook,
    save_apprentice,
    save_spellbook,
)
from jsonpatchx import GenericOperationRegistry, JSONValue, StandardRegistry
from jsonpatchx.fastapi import JsonPatchRoute
from jsonpatchx.pydantic import JsonPatchFor

STRICT_JSON_PATCH = True

app = create_app(
    title="Demo 4: Spellbook rune pointers",
    description=(
        "Registry-scoped rune pointer backends for spellbook and apprentice settings. "
        "Uses `JsonPatchRoute` to align OpenAPI and runtime validation."
    ),
)

registry = GenericOperationRegistry[
    StandardRegistry, IncrementOp, AppendOp, RunePointer
]
SpellbookPatch = JsonPatchFor[Literal["Spellbook"], registry]
ApprenticePatch = JsonPatchFor[Apprentice, registry]
spellbook_patch = JsonPatchRoute(
    SpellbookPatch,
    examples={
        "midnight-runes": {
            "summary": "toggle ritual and restock ingredients",
            "value": [
                {"op": "replace", "path": "rituals.summon.enabled", "value": True},
                {"op": "increment", "path": "ingredients.moon_salt", "value": 5},
            ],
        }
    },
    strict_content_type=STRICT_JSON_PATCH,
)
apprentice_patch = JsonPatchRoute(
    ApprenticePatch,
    examples={
        "sparkle-sprint": {
            "summary": "boost mana and add a sigil",
            "value": [
                {"op": "increment", "path": "mana", "value": 20},
                {"op": "append", "path": "sigils", "value": "aurora"},
            ],
        },
        "lantern-lesson": {
            "summary": "rename and add a sigil",
            "value": [
                {"op": "replace", "path": "name", "value": "Nova"},
                {"op": "append", "path": "sigils", "value": "ember"},
            ],
        },
    },
    strict_content_type=STRICT_JSON_PATCH,
)


@app.get(
    "/spellbooks/{spellbook_id}",
    response_model=JSONValue,
    tags=["spellbooks"],
    summary="Get a spellbook",
    description="Fetch a spellbook by id.",
)
def get_spellbook_endpoint(
    spellbook_id: Annotated[
        SpellbookId,
        Path(...),
    ],
) -> JSONValue:
    doc = get_spellbook(spellbook_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="spellbook not found")
    return doc


@app.patch(
    "/spellbooks/{spellbook_id}",
    response_model=JSONValue,
    tags=["spellbooks"],
    summary="Patch a spellbook (rune pointers)",
    description="Use rune pointers like 'rituals.summon.enabled'.",
    **spellbook_patch.route_kwargs(),
)
def patch_spellbook(
    spellbook_id: Annotated[
        SpellbookId,
        Path(...),
    ],
    patch: Annotated[
        SpellbookPatch,
        Depends(spellbook_patch.dependency()),
    ],
) -> JSONValue:
    doc = get_spellbook(spellbook_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="spellbook not found")
    updated = patch.apply(doc)
    save_spellbook(spellbook_id, updated)
    return updated


@app.get(
    "/apprentices/{apprentice_id}",
    response_model=Apprentice,
    tags=["apprentices"],
    summary="Get an apprentice",
    description="Fetch an apprentice by id.",
)
def get_apprentice_endpoint(
    apprentice_id: Annotated[
        ApprenticeId,
        Path(...),
    ],
) -> Apprentice:
    apprentice = get_apprentice(apprentice_id)
    if apprentice is None:
        raise HTTPException(status_code=404, detail="apprentice not found")
    return apprentice


@app.patch(
    "/apprentices/{apprentice_id}",
    response_model=Apprentice,
    tags=["apprentices"],
    summary="Patch an apprentice (rune pointers)",
    description="Use rune pointers like 'mana' or 'sigils.0'.",
    **apprentice_patch.route_kwargs(),
)
def patch_apprentice(
    apprentice_id: Annotated[
        ApprenticeId,
        Path(...),
    ],
    patch: Annotated[
        ApprenticePatch,
        Depends(apprentice_patch.dependency()),
    ],
) -> Apprentice:
    apprentice = get_apprentice(apprentice_id)
    if apprentice is None:
        raise HTTPException(status_code=404, detail="apprentice not found")
    updated = patch.apply(apprentice)
    save_apprentice(apprentice_id, updated)
    return updated
