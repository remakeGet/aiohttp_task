import pydantic
from datetime import datetime
from errors import HttpError

class BaseAdvertisementRequest(pydantic.BaseModel):
    title: str
    description: str
    owner: str
    
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
    
    @pydantic.field_validator("owner")
    @classmethod
    def validate_owner(cls, v: str):
        if len(v) < 2:
            raise ValueError("owner name must be at least 2 characters long")
        if len(v) > 100:
            raise ValueError("owner name must be at most 100 characters long")
        return v

class CreateAdvertisementRequest(BaseAdvertisementRequest):
    pass

class UpdateAdvertisementRequest(pydantic.BaseModel):
    title: str | None = None
    description: str | None = None
    owner: str | None = None
    created_at: datetime | None = None
    
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
    
    @pydantic.field_validator("owner")
    @classmethod
    def validate_owner(cls, v: str | None):
        if v is not None:
            if len(v) < 2:
                raise ValueError("owner name must be at least 2 characters long")
            if len(v) > 100:
                raise ValueError("owner name must be at most 100 characters long")
        return v

def validate(schema: type[CreateAdvertisementRequest | UpdateAdvertisementRequest], json_data: dict):
    try:
        schema_instance = schema(**json_data)
        return schema_instance.model_dump(exclude_unset=True)
    except pydantic.ValidationError as e:
        errors = e.errors()
        for error in errors:
            error.pop("ctx", None)
        raise HttpError(400, errors)