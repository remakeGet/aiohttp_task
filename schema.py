import pydantic
from datetime import datetime
from errors import HttpError


class UserCreate(pydantic.BaseModel):
    email: str
    password: str


class UserLogin(pydantic.BaseModel):
    email: str
    password: str


class CreateAdvertisementRequest(pydantic.BaseModel):
    title: str
    description: str
    
    @pydantic.field_validator("title")
    @classmethod
    def validate_title(cls, v: str):
        if len(v) < 3:
            raise ValueError("title must be at least 3 characters long")
        if len(v) > 200:
            raise ValueError("title must be at most 200 characters long")
        return v
    
    @pydantic.field_validator("description")
    @classmethod
    def validate_description(cls, v: str):
        if len(v) < 10:
            raise ValueError("description must be at least 10 characters long")
        return v

class UpdateAdvertisementRequest(pydantic.BaseModel):
    title: str | None = None
    description: str | None = None
    
    @pydantic.field_validator("title")
    @classmethod
    def validate_title(cls, v: str | None):
        if v is not None:
            if len(v) < 3:
                raise ValueError("title must be at least 3 characters long")
            if len(v) > 200:
                raise ValueError("title must be at most 200 characters long")
        return v
    
    @pydantic.field_validator("description")
    @classmethod
    def validate_description(cls, v: str | None):
        if v is not None and len(v) < 10:
            raise ValueError("description must be at least 10 characters long")
        return v


def validate(schema: type[pydantic.BaseModel], json_data: dict):
    try:
        schema_instance = schema(**json_data)
        return schema_instance.model_dump(exclude_unset=True)
    except pydantic.ValidationError as e:
        errors = e.errors()
        for error in errors:
            error.pop("ctx", None)
        raise HttpError(400, errors)