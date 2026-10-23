from pydantic import BaseModel, ConfigDict


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ListResponse[T](ApiModel):
    items: list[T]
    total: int


class ErrorBody(ApiModel):
    code: str
    message: str
    request_id: str | None = None
    details: list | dict | None = None


class ErrorResponse(ApiModel):
    """Documented so the OpenAPI spec shows the envelope on every non-2xx response."""

    error: ErrorBody
