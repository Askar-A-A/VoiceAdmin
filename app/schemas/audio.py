from pydantic import BaseModel


class UploadResult(BaseModel):
    success: bool
    name: str | None = None
    error: str | None = None
