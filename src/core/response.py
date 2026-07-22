from typing import Any

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from src.schemas.response import ApiResponseModel, ErrorDetailModel, MetadataModel


class ApiResponse(JSONResponse):
    """
    Standard API response wrapper.

    Automatically determines success/error
    based on the presence of an error object.
    """

    def __init__(
        self,
        *,
        success: bool = True,
        message: str | None = None,
        data: Any = None,
        error: ErrorDetailModel | None = None,
        metadata: MetadataModel | None = None,
        status_code: int | None = None,
        headers: dict[str, str] | None = None,
    ):
        success = error is None

        if status_code is None:
            status_code = 200 if success else 500

        payload: ApiResponseModel = ApiResponseModel(
            success=success,
            message=message if success else None,
            data=data if success else None,
            error=error,
            metadata=metadata or MetadataModel(),
        )

        super().__init__(
            status_code=status_code,
            headers=headers,
            content=jsonable_encoder(
                payload,
                exclude_none=True,
            ),
        )
