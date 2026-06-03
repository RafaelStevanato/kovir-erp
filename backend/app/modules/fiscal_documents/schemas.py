from __future__ import annotations

from pydantic import BaseModel, Field


class FiscalDocumentCancelRequest(BaseModel):
    justificativa: str = Field(min_length=15, max_length=255)
