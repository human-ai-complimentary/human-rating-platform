from __future__ import annotations

import csv
import io
import logging
import sys
from typing import Any

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Question, Upload
from .mappers import build_upload_response
from .queries import fetch_experiment_or_404
from .validators import validate_csv_required_fields, validate_csv_upload

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 200 * 1024 * 1024  # 200MB


def _configure_csv_field_limit() -> None:
    """Raise Python's per-field CSV cap so long-context rows can be parsed."""
    limit = sys.maxsize
    while True:
        try:
            csv.field_size_limit(limit)
            return
        except OverflowError:
            limit //= 10


def _get_upload_size(file: UploadFile) -> int:
    """Measure the uploaded file without loading it fully into memory."""
    stream = file.file
    current = stream.tell()
    stream.seek(0, io.SEEK_END)
    size = stream.tell()
    stream.seek(current)
    return size


async def upload_questions_csv(
    experiment_id: int,
    file: UploadFile,
    db: AsyncSession,
) -> dict[str, str]:
    await fetch_experiment_or_404(experiment_id, db)
    validate_csv_upload(file)
    _configure_csv_field_limit()

    if _get_upload_size(file) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File size exceeds 200MB limit")

    await file.seek(0)
    text_stream = io.TextIOWrapper(file.file, encoding="utf-8", newline="")
    try:
        reader = csv.DictReader(text_stream)
        required_fields = ["question_id", "question_text"]
        questions_added = 0

        for row in reader:
            validate_csv_required_fields(row, required_fields)
            db.add(
                Question(
                    experiment_id=experiment_id,
                    question_id=row["question_id"],
                    question_text=row["question_text"],
                    gt_answer=row.get("gt_answer") or "",
                    options=row.get("options") or "",
                    question_type=row.get("question_type") or "MC",
                    extra_data=row.get("metadata") or "{}",
                )
            )
            questions_added += 1
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded") from exc
    except csv.Error as exc:
        raise HTTPException(status_code=400, detail=f"Invalid CSV file: {exc}") from exc
    finally:
        try:
            text_stream.detach()
        except Exception:
            pass

    db.add(
        Upload(
            experiment_id=experiment_id,
            filename=file.filename,
            question_count=questions_added,
        )
    )
    await db.commit()

    logger.info(
        "Question batch uploaded",
        extra={
            "attributes": {
                "experiment_id": experiment_id,
                "question_count": questions_added,
                "filename": file.filename,
            }
        },
    )

    return {"message": f"Uploaded {questions_added} questions"}


async def list_uploads(
    experiment_id: int,
    skip: int,
    limit: int,
    db: AsyncSession,
) -> list[dict[str, Any]]:
    await fetch_experiment_or_404(experiment_id, db)

    uploads = (
        (
            await db.execute(
                select(Upload)
                .where(Upload.experiment_id == experiment_id)
                .order_by(Upload.uploaded_at.desc())
                .offset(skip)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )

    return [build_upload_response(upload) for upload in uploads]
