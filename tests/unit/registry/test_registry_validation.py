from __future__ import annotations

from abc import abstractmethod
from typing import Annotated, ClassVar, Final, Literal, Union, override

import pytest
from pytest import Subtests

from jsonpatchx.builtins import AddOp, RemoveOp
from jsonpatchx.builtins import TestOp as BuiltinTestOp
from jsonpatchx.exceptions import InvalidOperationRegistry, OperationNotRecognized
from jsonpatchx.registry import StandardRegistry, _RegistrySpec
from jsonpatchx.schema import OperationSchema
from jsonpatchx.types import JSONValue


def test_invalid_registry_typeforms(subtests: Subtests) -> None:
    class Dup1Op(OperationSchema):
        op: Literal["dup"] = "dup"

        @override
        def apply(self, doc: JSONValue) -> JSONValue:  # pragma: no cover
            return doc

    class Dup2Op(OperationSchema):
        op: Literal["dup"] = "dup"

        @override
        def apply(self, doc: JSONValue) -> JSONValue:  # pragma: no cover
            return doc

    class AbstractOp(OperationSchema):
        op: Literal["abstract"] = "abstract"

        @abstractmethod
        def apply(self, doc: JSONValue) -> JSONValue:  # pragma: no cover
            raise NotImplementedError

    with subtests.test("duplicate op literals are rejected"):
        with pytest.raises(InvalidOperationRegistry):
            _RegistrySpec.from_typeform(Dup1Op | Dup2Op)

    with subtests.test("duplicate operation class names are rejected"):

        class TestOp(OperationSchema):
            op: Literal["custom-test"] = "custom-test"

            @override
            def apply(self, doc: JSONValue) -> JSONValue:  # pragma: no cover
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
            _RegistrySpec.from_typeform(Final[BuiltinTestOp])

        with pytest.raises(InvalidOperationRegistry):
            _RegistrySpec.from_typeform(ClassVar[BuiltinTestOp])


def test_valid_registry_typeforms(subtests: Subtests) -> None:
    with subtests.test("valid registry from union of ops"):
        spec_from_union = _RegistrySpec.from_typeform(AddOp | RemoveOp)
        assert spec_from_union.ops == frozenset({AddOp, RemoveOp})
        spec_from_union = _RegistrySpec.from_typeform(Union[AddOp, RemoveOp])
        assert spec_from_union.ops == frozenset({AddOp, RemoveOp})

    with subtests.test("valid registry from single op"):
        spec_from_non_union = _RegistrySpec.from_typeform(AddOp)
        assert spec_from_non_union.ops == frozenset({AddOp})

    with subtests.test("valid registry from nested type aliases"):
        type AliasA = AddOp
        type AliasB = RemoveOp
        type NestedAlias = AliasA | AliasB

        spec_from_alias = _RegistrySpec.from_typeform(NestedAlias)
        assert spec_from_alias.ops == frozenset({AddOp, RemoveOp})

    with subtests.test("valid registry from Annotated type"):
        spec_from_annotated = _RegistrySpec.from_typeform(
            Annotated[AddOp | RemoveOp, "metadata"]
        )
        assert spec_from_annotated.ops == frozenset({AddOp, RemoveOp})

    with subtests.test("registry equivalence"):
        type AliasA = Annotated[AddOp, "meta"]
        type AliasB = RemoveOp
        spec_from_union = _RegistrySpec.from_typeform(
            Union[AliasA, AddOp, AliasB, Annotated[RemoveOp, BuiltinTestOp]]
        )

        assert spec_from_union == _RegistrySpec.from_typeform(RemoveOp | AddOp)
        assert spec_from_union != _RegistrySpec.from_typeform(
            Union[AddOp, RemoveOp, BuiltinTestOp]
        )
        assert (spec_from_union == Union[AddOp, RemoveOp]) is False


def test_registry_spec_repr_hash_equality_are_set_based() -> None:
    registry_a = _RegistrySpec.from_typeform(AddOp | RemoveOp)
    registry_b = _RegistrySpec.from_typeform(RemoveOp | AddOp)

    assert registry_a == registry_b
    assert hash(registry_a) == hash(registry_b)


def test_registry_spec_model_for_and_unknown_rejection() -> None:
    registry = _RegistrySpec.from_typeform(BuiltinTestOp)
    assert registry.model_for("test") is BuiltinTestOp
    with pytest.raises(OperationNotRecognized):
        registry.model_for("not-allowed")


def test_registry_spec_is_rfc6902_flag() -> None:
    standard = _RegistrySpec.from_typeform(StandardRegistry)
    assert standard.is_rfc6902 is True

    custom = _RegistrySpec.from_typeform(BuiltinTestOp)
    assert custom.is_rfc6902 is False
