from typing import Any

import email_validator
from pydantic import BaseModel, GetCoreSchemaHandler
from pydantic_core import core_schema


class _EmailStr(str):
    """EmailStr variant that also accepts RFC 2606 reserved .test addresses."""

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source: type[Any],
        handler: GetCoreSchemaHandler,
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_plain_validator_function(
            cls._validate,
            serialization=core_schema.to_string_ser_schema(),
        )

    @classmethod
    def __get_pydantic_json_schema__(cls, schema: Any, handler: Any) -> dict[str, Any]:
        return {"type": "string", "format": "email"}

    @classmethod
    def _validate(cls, value: Any) -> "_EmailStr":
        if not isinstance(value, str):
            raise ValueError("string required")
        result = email_validator.validate_email(
            value,
            check_deliverability=False,
            test_environment=True,
        )
        return cls(result.normalized)


# Public alias — consumers import this as EmailStr
EmailStr = _EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    email: EmailStr
    role: str


class Me(BaseModel):
    email: EmailStr
    role: str
