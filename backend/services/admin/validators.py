from __future__ import annotations

from typing import Any

from fastapi import HTTPException, UploadFile


def validate_csv_upload(file: UploadFile) -> None:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV file")


def validate_csv_required_fields(row: dict[str, Any], required_fields: list[str]) -> None:
    for field in required_fields:
        if field not in row:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
