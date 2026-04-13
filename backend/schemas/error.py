"""Pydantic schemas for the standard error envelope.

Including these in route ``responses=`` makes them appear in the OpenAPI
schema so consumers know the exact error shape.
"""
from typing import Any, Dict, Optional
from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str = ""
    details: Dict[str, Any] = {}


class ErrorEnvelope(BaseModel):
    error: ErrorDetail
