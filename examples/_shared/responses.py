from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse
from pydantic import BaseModel

from jsonpatch.exceptions import PatchApplyFailed, PatchError


class PatchFailureDetailResponse(BaseModel):
    index: int
    op: dict[str, Any]
    message: str
    cause_type: str | None = None


class PatchErrorResponse(BaseModel):
    detail: str | PatchFailureDetailResponse


def patch_error_response(exc: PatchError) -> JSONResponse:
    if isinstance(exc, PatchApplyFailed):
        detail = exc.detail
        payload = PatchFailureDetailResponse(
            index=detail.index,
            op=detail.op.model_dump(mode="json", by_alias=True),
            message=detail.message,
            cause_type=detail.cause_type,
        )
        return JSONResponse(
            status_code=400, content=PatchErrorResponse(detail=payload).model_dump()
        )

    return JSONResponse(
        status_code=400, content=PatchErrorResponse(detail=str(exc)).model_dump()
    )


def patch_error_responses() -> dict[int, dict[str, Any]]:
    return {
        400: {
            "description": "Patch application error",
            "content": {
                "application/json": {
                    "schema": PatchErrorResponse.model_json_schema(
                        ref_template="#/components/schemas/{model}"
                    )
                }
            },
        }
    }
