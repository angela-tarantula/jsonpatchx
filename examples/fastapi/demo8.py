"""Demo 8: JSONSelector operations with generic and custom selector backends."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Annotated, Generic, Literal, cast, override

from fastapi import HTTPException, Path
from pydantic import ConfigDict, Field
from typing_extensions import TypeVar

from examples.fastapi.shared import ConfigId, create_app, get_config, save_config
from jsonpatchx import JSONSelector, JSONValue, OperationSchema
from jsonpatchx.backend import (
    _DEFAULT_POINTER_CLS,
    _DEFAULT_SELECTOR_CLS,
    PointerBackend,
    SelectorBackend,
    SelectorMatch,
)
from jsonpatchx.fastapi import JsonPatchRoute
from jsonpatchx.pydantic import JsonPatchFor
from jsonpatchx.types import JSONBoolean, JSONNumber

STRICT_JSON_PATCH = True


class JSONPathSelectorV2(_DEFAULT_SELECTOR_CLS):
    """Marker subclass used when specializing a generic selector backend."""


S = TypeVar("S", bound=JSONPathSelectorV2, covariant=True, default=JSONPathSelectorV2)


@dataclass(frozen=True, slots=True)
class DotStarMatch(SelectorMatch):
    obj: JSONValue
    parts: tuple[int | str, ...]

    @override
    def pointer(self) -> PointerBackend:
        return cast(PointerBackend, _DEFAULT_POINTER_CLS.from_parts(self.parts))


class DotStarSelector(SelectorBackend):
    """
    Minimal custom selector backend using dot-separated object segments.

    Supported syntax is intentionally small:
    - `features.chat`
    - `features.*`
    - `rituals.*.enabled`

    `*` means "all object members at this level". Arrays are not supported.
    """

    __slots__ = ("_selector", "_segments")

    def __init__(self, selector: str) -> None:
        parts = tuple(selector.split("."))
        if not selector or any(not part for part in parts):
            raise ValueError(f"invalid dot-star selector: {selector!r}")
        self._selector = selector
        self._segments = parts

    @override
    def pointers(self, doc: JSONValue) -> Iterable[PointerBackend]:
        return [match.pointer() for match in self.finditer(doc)]

    @override
    def finditer(self, doc: JSONValue) -> Iterable[SelectorMatch]:
        matches: list[DotStarMatch] = [DotStarMatch(doc, ())]

        for segment in self._segments:
            next_matches: list[DotStarMatch] = []
            for match in matches:
                current = match.obj
                if not isinstance(current, dict):
                    raise TypeError(
                        f"selector segment {segment!r} requires an object target"
                    )

                if segment == "*":
                    next_matches.extend(
                        DotStarMatch(value, match.parts + (key,))
                        for key, value in current.items()
                    )
                    continue

                next_matches.append(
                    DotStarMatch(current[segment], match.parts + (segment,))
                )

            matches = next_matches

        return matches

    @override
    def __str__(self) -> str:
        return self._selector


class GenericIncrementEachOp(OperationSchema, Generic[S]):
    model_config = ConfigDict(
        title="Increment selected numbers",
        json_schema_extra={
            "description": "Increment every numeric match produced by a generic JSONSelector backend."
        },
    )

    op: Literal["generic_increment_each"] = "generic_increment_each"
    path: JSONSelector[JSONNumber, S]
    value: JSONNumber = Field(gt=0)

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        for pointer in self.path.get_pointers(doc):
            current = pointer.get(doc)
            doc = pointer.add(doc, current + self.value)
        return doc


class ToggleSelectedFlagsOp(OperationSchema):
    model_config = ConfigDict(
        title="Toggle selected flags",
        json_schema_extra={
            "description": "Toggle every boolean matched by JsonPatchX's built-in JSONPath selector backend."
        },
    )

    op: Literal["toggle_selected_flags"] = "toggle_selected_flags"
    path: JSONSelector[JSONBoolean]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        for pointer in self.path.get_pointers(doc):
            current = pointer.get(doc)
            doc = pointer.add(doc, not current)
        return doc


class SetSelectedFlagsOp(OperationSchema):
    model_config = ConfigDict(
        title="Set selected flags",
        json_schema_extra={
            "description": "Set every boolean matched by a custom selector backend to the same value."
        },
    )

    op: Literal["set_selected_flags"] = "set_selected_flags"
    path: JSONSelector[JSONBoolean, DotStarSelector]
    value: JSONBoolean

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        return self.path.addall(doc, self.value)


type ConfigRegistry = (
    GenericIncrementEachOp[JSONPathSelectorV2]
    | ToggleSelectedFlagsOp
    | SetSelectedFlagsOp
)
ConfigPatch = JsonPatchFor[Literal["ServiceConfig"], ConfigRegistry]
config_patch = JsonPatchRoute(
    ConfigPatch,
    examples={
        "jsonpath-default": {
            "summary": "toggle every feature flag via the built-in JSONPath backend",
            "value": [
                {"op": "toggle_selected_flags", "path": "$.features.*"},
            ],
        },
        "selector-sweep": {
            "summary": "increment every numeric limit and enable every feature flag",
            "value": [
                {"op": "generic_increment_each", "path": "$.limits.*", "value": 5},
                {"op": "set_selected_flags", "path": "features.*", "value": True},
            ],
        },
    },
    strict_content_type=STRICT_JSON_PATCH,
)

app = create_app(
    title="JSONSelector-powered config patches",
    description=(
        "Demo 8: Config patching with JSONSelector operations using the built-in "
        "JSONPath backend, a generic selector-backend parameter, and a custom "
        "selector backend implementation."
    ),
)


@app.get(
    "/configs/{config_id}",
    response_model=JSONValue,
    tags=["configs"],
    summary="Get a service config",
    description="Fetch a service config by id.",
)
def get_config_endpoint(
    config_id: Annotated[
        ConfigId,
        Path(...),
    ],
) -> JSONValue:
    doc = get_config(config_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="config not found")
    return doc


@app.patch(
    "/configs/{config_id}",
    response_model=JSONValue,
    tags=["configs"],
    summary="Patch a service config with selectors",
    description="Apply JSONSelector-based custom operations to a service config.",
    **config_patch.route_kwargs(),
)
def patch_config(
    config_id: Annotated[
        ConfigId,
        Path(...),
    ],
    patch: Annotated[ConfigPatch, config_patch.Body()],
) -> JSONValue:
    doc = get_config(config_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="config not found")
    updated = patch.apply(doc)
    save_config(config_id, updated)
    return updated
