from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class ImportTarget(str, Enum):
    PARTICIPANTS = "participants"
    PRODUCTS = "products"
    FISCAL_CLASSIFICATIONS = "fiscal-classifications"


ImportRowStatus = Literal["valid", "invalid"]
ImportCellValue = str | int | float | bool | None

MAX_IMPORT_ROWS = 5000
MAX_IMPORT_COLUMNS = 120
MAX_IMPORT_COLUMN_KEY_LENGTH = 100
MAX_IMPORT_CELL_LENGTH = 2000


class ImportRowsRequest(BaseModel):
    company_id: str | None = Field(default=None, min_length=1)
    rows: list[dict[str, ImportCellValue]] = Field(default_factory=list, max_length=MAX_IMPORT_ROWS)

    @field_validator("company_id", mode="before")
    @classmethod
    def clean_company_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("rows")
    @classmethod
    def validate_rows(cls, rows: list[dict[str, ImportCellValue]]) -> list[dict[str, ImportCellValue]]:
        for row_index, row in enumerate(rows, start=2):
            if len(row) > MAX_IMPORT_COLUMNS:
                raise ValueError(
                    f"Linha {row_index} excede o limite de {MAX_IMPORT_COLUMNS} colunas por importacao."
                )

            for key, value in row.items():
                cleaned_key = key.strip()
                if not cleaned_key:
                    raise ValueError(f"Linha {row_index} possui coluna sem nome.")
                if len(cleaned_key) > MAX_IMPORT_COLUMN_KEY_LENGTH:
                    raise ValueError(
                        f"Linha {row_index} possui coluna acima de {MAX_IMPORT_COLUMN_KEY_LENGTH} caracteres."
                    )
                if isinstance(value, str) and len(value) > MAX_IMPORT_CELL_LENGTH:
                    raise ValueError(
                        f"Linha {row_index}, coluna {cleaned_key}, excede {MAX_IMPORT_CELL_LENGTH} caracteres."
                    )

        return rows


class ImportTemplateColumn(BaseModel):
    key: str
    label: str
    required: bool = False
    description: str
    example: str | None = None


class ImportTemplate(BaseModel):
    target: ImportTarget
    label: str
    description: str
    columns: list[ImportTemplateColumn]


class ImportRowPreview(BaseModel):
    row_number: int
    status: ImportRowStatus
    raw: dict[str, Any]
    payload: dict[str, Any] | None = None
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ImportPreviewResult(BaseModel):
    target: ImportTarget
    company_id: str
    total_rows: int
    valid_rows: int
    invalid_rows: int
    rows: list[ImportRowPreview]


class ImportCommitCreatedRow(BaseModel):
    row_number: int
    id: str | None = None
    payload: dict[str, Any]
    result: dict[str, Any]


class ImportCommitFailedRow(BaseModel):
    row_number: int
    payload: dict[str, Any] | None = None
    errors: list[str]


class ImportCommitResult(BaseModel):
    target: ImportTarget
    company_id: str
    total_rows: int
    created_rows: int
    failed_rows: int
    skipped_rows: int
    created: list[ImportCommitCreatedRow]
    failures: list[ImportCommitFailedRow]
