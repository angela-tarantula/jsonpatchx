from __future__ import annotations

from abc import abstractmethod
from typing import Annotated, ClassVar, Final, Literal, Union, override

import pytest
from pytest import Subtests

from jsonpatchx.builtins import TestOp as BuiltinTestOp
from jsonpatchx.exceptions import InvalidOperationRegistry, OperationNotRecognized
from jsonpatchx.registry import StandardRegistry, _RegistrySpec
from jsonpatchx.schema import OperationSchema
from jsonpatchx.types import JSONValue


class ToggleOp(OperationSchema):
    op: Literal["toggle"] = "toggle"
    path: str

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        return doc


def test_invalid_registry_typeforms(subtests: Subtests) -> None:
    class FirstOp(OperationSchema):
        op: Literal["dup"] = "dup"

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return doc

    class SecondOp(OperationSchema):
        op: Literal["dup"] = "dup"

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return doc

    class AbstractOp(OperationSchema):
        op: Literal["abstract"] = "abstract"

        @abstractmethod
        def apply(self, doc: JSONValue) -> JSONValue:
            raise NotImplementedError

    with subtests.test("duplicate op literals are rejected"):
        with pytest.raises(InvalidOperationRegistry):
            _RegistrySpec.from_typeform(FirstOp | SecondOp)

    with subtests.test("duplicate operation class names are rejected"):

        class TestOp(OperationSchema):
            op: Literal["custom-test"] = "custom-test"

            @override
            def apply(self, doc: JSONValue) -> JSONValue:
                return doc

        with pytest.raises(
            InvalidOperationRegistry,
            match=r"Expected unique OperationSchema names.*TestOp",
        ):
            _RegistrySpec.from_typeform(BuiltinTestOp | TestOp)

    with subtests.test("non-OperationSchema inputs are rejected"):
        with pytest.raises(
            InvalidOperationRegistry,
            match="registry must be a union of concrete OperationSchemas",
        ):
            _RegistrySpec.from_typeform(str)

        with pytest.raises(
            InvalidOperationRegistry,
            match="registry must be a union of concrete OperationSchemas",
        ):
            _RegistrySpec.from_typeform(42)

    with subtests.test("OperationSchema base class is rejected"):
        with pytest.raises(InvalidOperationRegistry):
            _RegistrySpec.from_typeform(OperationSchema)

    with subtests.test("abstract operation classes are rejected"):
        with pytest.raises(InvalidOperationRegistry):
            _RegistrySpec.from_typeform(AbstractOp)

    with subtests.test("unsupported type expressions are rejected"):
        with pytest.raises(InvalidOperationRegistry):
            _RegistrySpec.from_typeform(Final[ToggleOp])

        with pytest.raises(InvalidOperationRegistry):
            _RegistrySpec.from_typeform(ClassVar[ToggleOp])


def test_valid_registry_typeforms(subtests: Subtests) -> None:
    class OpA(OperationSchema):
        op: Literal["a"] = "a"

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return doc

    class OpB(OperationSchema):
        op: Literal["b"] = "b"

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return doc

    with subtests.test("valid registry from union of ops"):
        spec_from_union = _RegistrySpec.from_typeform(OpA | OpB)
        assert spec_from_union.ops == frozenset({OpA, OpB})
        spec_from_union = _RegistrySpec.from_typeform(Union[OpA, OpB])
        assert spec_from_union.ops == frozenset({OpA, OpB})

    with subtests.test("valid registry from single op"):
        spec_from_non_union = _RegistrySpec.from_typeform(OpA)
        assert spec_from_non_union.ops == frozenset({OpA})

    with subtests.test("valid registry from nested type aliases"):
        type AliasA = OpA
        type AliasB = OpB
        type NestedAlias = AliasA | AliasB

        spec_from_alias = _RegistrySpec.from_typeform(NestedAlias)
        assert spec_from_alias.ops == frozenset({OpA, OpB})

    with subtests.test("valid registry from Annotated type"):
        spec_from_annotated = _RegistrySpec.from_typeform(
            Annotated[OpA | OpB, "metadata"]
        )
        assert spec_from_annotated.ops == frozenset({OpA, OpB})

    with subtests.test("registry equivalence"):
        type AliasA = Annotated[OpA, "meta"]
        type AliasB = OpB
        spec_from_union = _RegistrySpec.from_typeform(
            Union[AliasA, OpA, AliasB, Annotated[OpB, BuiltinTestOp]]
        )

        assert spec_from_union == _RegistrySpec.from_typeform(OpB | OpA)
        assert spec_from_union != _RegistrySpec.from_typeform(
            Union[OpA, OpB, BuiltinTestOp]
        )
        assert (spec_from_union == Union[OpA, OpB]) is False


def test_registry_spec_repr_hash_equality_are_set_based() -> None:
    class FirstOp(OperationSchema):
        op: Literal["cache-first"] = "cache-first"

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return doc

    class SecondOp(OperationSchema):
        op: Literal["cache-second"] = "cache-second"

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return doc

    registry_a = _RegistrySpec.from_typeform(FirstOp | SecondOp)
    registry_b = _RegistrySpec.from_typeform(SecondOp | FirstOp)

    assert registry_a == registry_b
    assert hash(registry_a) == hash(registry_b)


def test_registry_spec_model_for_and_unknown_rejection() -> None:
    registry = _RegistrySpec.from_typeform(ToggleOp)
    assert registry.model_for("toggle") is ToggleOp
    with pytest.raises(OperationNotRecognized):
        registry.model_for("not-allowed")


def test_registry_spec_is_rfc6902_flag() -> None:
    standard = _RegistrySpec.from_typeform(StandardRegistry)
    assert standard.is_rfc6902 is True

    custom = _RegistrySpec.from_typeform(ToggleOp)
    assert custom.is_rfc6902 is False
