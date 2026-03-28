from operator import attrgetter

import pytest

from jsonpatchx import JSONPointer
from tests.compliance.rfc6901.cases import DOC, POINTER_CASES, Case


@pytest.mark.parametrize("case", POINTER_CASES, ids=attrgetter("id"))
def test_json_pointer_core(case: Case) -> None:
    if "fail" not in case.model_fields_set:
        ptr = JSONPointer.parse(case.pointer)
        assert ptr.get(DOC) == case.expected
    else:
        with pytest.raises(Exception):
            ptr = JSONPointer.parse(case.pointer)
            print(ptr.get(DOC))
