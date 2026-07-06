"""Structured ClusterFuzzLite harness for custom pointer backends and registries."""

import copy
import json
import sys
from collections.abc import Iterable
from typing import Literal, Self, cast, override

import atheris  # type: ignore[import-untyped]

from fuzzers._fuzz_shared import (
    ByteCursor,
    Outcome,
    assert_equivalent,
    coerce_patch,
    random_dot_path,
    random_json_value,
    random_patch,
    random_rfc6901_path,
)

with atheris.instrument_imports():
    from pydantic import ValidationError

    from jsonpatchx import (
        JsonPatch,
        JSONPointer,
        JSONValue,
        StandardRegistry,
        apply_patch,
    )
    from jsonpatchx.exceptions import (
        InvalidJSONPointer,
        PatchConflictError,
        PatchError,
        PatchInternalError,
    )
    from jsonpatchx.schema import OperationSchema
    from jsonpatchx.types import JSONNumber


class DotPointer:
    """Simple dot-delimited pointer backend used only by this fuzz target."""

    __slots__ = ("_parts",)

    def __init__(self, pointer: str) -> None:
        if pointer.startswith(".") or pointer.endswith(".") or ".." in pointer:
            raise ValueError("invalid dot pointer")
        if "/" in pointer:
            raise ValueError("dot pointer cannot contain '/'")
        self._parts = tuple(pointer.split(".")) if pointer else ()

    @property
    def parts(self) -> tuple[str, ...]:
        return self._parts

    @classmethod
    def from_parts(cls, parts: Iterable[str]) -> Self:
        return cls(".".join(parts))

    def resolve(self, doc: JSONValue) -> JSONValue:
        current: JSONValue = doc
        for token in self._parts:
            if isinstance(current, dict):
                current = current[token]
                continue
            if isinstance(current, list):
                index = int(token)
                current = current[index]
                continue
            raise TypeError("cannot resolve child token from non-container")
        return current

    @override
    def __str__(self) -> str:
        return ".".join(self._parts)


class DotSetOp(OperationSchema):
    op: Literal["dot_set"] = "dot_set"
    path: JSONPointer[JSONValue, DotPointer]
    value: JSONValue

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        return self.path.add(doc, self.value)


class DotRemoveOp(OperationSchema):
    op: Literal["dot_remove"] = "dot_remove"
    path: JSONPointer[JSONValue, DotPointer]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        return self.path.remove(doc)


class DotIncrementOp(OperationSchema):
    op: Literal["dot_increment"] = "dot_increment"
    path: JSONPointer[JSONNumber, DotPointer]
    value: JSONNumber

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        return self.path.add(doc, current + self.value)


type HybridRegistry = StandardRegistry | DotSetOp | DotRemoveOp | DotIncrementOp


_KNOWN_OPS: tuple[str, ...] = (
    "add",
    "remove",
    "replace",
    "move",
    "copy",
    "test",
    "dot_set",
    "dot_remove",
    "dot_increment",
)
_UNKNOWN_OPS: tuple[str, ...] = ("", "noop", "dot-noop")
_ALL_OPS = _KNOWN_OPS + _UNKNOWN_OPS

_EXPECTED_PATCH_EXCEPTIONS = (
    PatchError,
    ValidationError,
    json.JSONDecodeError,
    UnicodeError,
)


def _error_bucket(error_type: type[BaseException]) -> str:
    if issubclass(error_type, PatchConflictError):
        return "conflict"
    if issubclass(error_type, (PatchError, ValidationError)):
        return "input"
    if issubclass(error_type, (json.JSONDecodeError, UnicodeError)):
        return "decode"
    return error_type.__name__


def _build_op(cursor: ByteCursor, op_name: str) -> dict[str, object]:
    use_dot = op_name.startswith("dot_")
    path = random_dot_path(cursor) if use_dot else random_rfc6901_path(cursor)

    op: dict[str, object] = {
        "op": op_name,
        "path": path,
    }

    if op_name in {"add", "replace", "test", "dot_set", "dot_increment"}:
        op["value"] = random_json_value(cursor)

    if op_name in {"copy", "move"}:
        op["from"] = random_rfc6901_path(cursor)

    if cursor.int_range(0, 6) == 0:
        op["x-fuzz"] = random_json_value(cursor, max_depth=2)

    return op


def _has_custom_ops(patch: list[dict[str, object]]) -> bool:
    for op in patch:
        op_name = op.get("op")
        if isinstance(op_name, str) and op_name.startswith("dot_"):
            return True
    return False


def _run_hybrid_patch(
    doc: object, patch: list[dict[str, object]], *, inplace: bool
) -> Outcome:
    try:
        patch_for_api = cast(list[dict[str, JSONValue]], patch)
        doc_for_api = cast(JSONValue, copy.deepcopy(doc))
        result = JsonPatch(patch_for_api, registry=HybridRegistry).apply(
            doc_for_api, inplace=inplace
        )
        return Outcome(value=result)
    except PatchInternalError:
        raise
    except _EXPECTED_PATCH_EXCEPTIONS as exc:
        return Outcome(error_type=type(exc))


def _run_hybrid_from_string(doc: object, patch: list[dict[str, object]]) -> Outcome:
    try:
        encoded_patch = json.dumps(patch, separators=(",", ":"), ensure_ascii=False)
        doc_for_api = cast(JSONValue, copy.deepcopy(doc))
        result = JsonPatch.from_string(encoded_patch, registry=HybridRegistry).apply(
            doc_for_api, inplace=False
        )
        return Outcome(value=result)
    except PatchInternalError:
        raise
    except _EXPECTED_PATCH_EXCEPTIONS as exc:
        return Outcome(error_type=type(exc))


def _run_standard_apply_patch(doc: object, patch: list[dict[str, object]]) -> Outcome:
    try:
        patch_for_api = cast(list[dict[str, JSONValue]], patch)
        doc_for_api = cast(JSONValue, copy.deepcopy(doc))
        result = apply_patch(doc_for_api, patch_for_api, inplace=False)
        return Outcome(value=result)
    except PatchInternalError:
        raise
    except _EXPECTED_PATCH_EXCEPTIONS as exc:
        return Outcome(error_type=type(exc))


def _exercise_dot_pointer(path: str, *, source: bytes) -> None:
    try:
        ptr: JSONPointer[JSONValue, DotPointer] = JSONPointer.parse(
            path, backend=DotPointer
        )
    except InvalidJSONPointer:
        return

    round_trip: JSONPointer[JSONValue, DotPointer] = JSONPointer.parse(
        str(ptr), backend=DotPointer
    )
    if tuple(ptr.parts) != tuple(round_trip.parts):
        raise AssertionError(
            "Dot pointer parse/string round-trip changed pointer parts"
        )

    cursor = ByteCursor(source)
    doc = random_json_value(cursor)
    value = random_json_value(cursor)

    gettable = ptr.is_gettable(copy.deepcopy(doc))
    try:
        ptr.get(copy.deepcopy(doc))
        get_ok = True
    except PatchError:
        get_ok = False
    if gettable != get_ok:
        raise AssertionError("Dot pointer is_gettable disagrees with get")

    addable = ptr.is_addable(copy.deepcopy(doc), value)
    try:
        ptr.add(copy.deepcopy(doc), value)
        add_ok = True
    except PatchError:
        add_ok = False
    if addable != add_ok:
        raise AssertionError("Dot pointer is_addable disagrees with add")


def _exercise_patch(doc: object, patch: list[dict[str, object]]) -> None:
    hybrid_copy = _run_hybrid_patch(doc, patch, inplace=False)
    hybrid_inplace = _run_hybrid_patch(doc, patch, inplace=True)
    hybrid_string = _run_hybrid_from_string(doc, patch)

    assert_equivalent(
        hybrid_copy,
        hybrid_inplace,
        context="Hybrid registry inplace=False vs inplace=True",
        error_bucket=_error_bucket,
    )
    assert_equivalent(
        hybrid_copy,
        hybrid_string,
        context="Hybrid registry python patch vs JSON string patch",
        error_bucket=_error_bucket,
    )

    if not _has_custom_ops(patch):
        standard = _run_standard_apply_patch(doc, patch)
        assert_equivalent(
            hybrid_copy,
            standard,
            context="Hybrid registry standard-only ops vs apply_patch",
            error_bucket=_error_bucket,
        )


def TestOneInput(data: bytes) -> None:
    if not data:
        return

    cursor = ByteCursor(data)
    generated_doc = random_json_value(cursor)
    generated_patch = random_patch(cursor, _ALL_OPS, _build_op)

    _exercise_dot_pointer(random_dot_path(cursor), source=data)
    _exercise_dot_pointer(data[:96].decode("latin-1"), source=data[::-1])
    _exercise_patch(generated_doc, generated_patch)

    try:
        payload = json.loads(data)
    except (json.JSONDecodeError, UnicodeError):
        return

    if isinstance(payload, dict):
        payload_patch = coerce_patch(payload.get("patch"))
        if payload_patch:
            _exercise_patch(payload.get("doc", generated_doc), payload_patch)
        return

    payload_patch = coerce_patch(payload)
    if payload_patch:
        _exercise_patch(generated_doc, payload_patch)


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
