from pydantic import BaseModel, ConfigDict


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid", str_strip_whitespace=True)


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int
