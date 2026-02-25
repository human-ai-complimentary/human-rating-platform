from __future__ import annotations

import csv
import io
from collections.abc import AsyncIterator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from models import Question, Rating, Rater
from .queries import fetch_experiment_or_404

EXPORT_COLUMNS = [
    "rating_id",
    "question_id",
    "question_text",
    "gt_answer",
    "rater_prolific_id",
    "rater_study_id",
    "rater_session_id",
    "answer",
    "confidence",
    "time_started",
    "time_submitted",
    "response_time_seconds",
]


def build_export_filename(experiment_id: int) -> str:
    return f"experiment_{experiment_id}_ratings.csv"


def _resolve_batch_size(batch_size: int | None) -> int:
    if batch_size is not None:
        return batch_size
    return get_settings().export_stream_batch_size


def _build_export_header_chunk() -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(EXPORT_COLUMNS)
    return output.getvalue()


def _build_export_row(
    rating: Rating,
    question: Question,
    rater: Rater,
) -> list[object]:
    response_time = (rating.time_submitted - rating.time_started).total_seconds()
    return [
        rating.id,
        question.question_id,
        question.question_text,
        question.gt_answer,
        rater.prolific_id,
        rater.study_id or "",
        rater.session_id or "",
        rating.answer,
        rating.confidence,
        rating.time_started.isoformat(),
        rating.time_submitted.isoformat(),
        round(response_time, 2),
    ]


async def stream_export_csv_chunks(
    *,
    experiment_id: int,
    db: AsyncSession,
    batch_size: int | None = None,
) -> AsyncIterator[str]:
    resolved_batch_size = _resolve_batch_size(batch_size)
    await fetch_experiment_or_404(experiment_id, db)

    yield _build_export_header_chunk()

    statement = (
        select(Rating, Question, Rater)
        .join(Question, Rating.question_id == Question.id)
        .join(Rater, Rating.rater_id == Rater.id)
        .where(Question.experiment_id == experiment_id)
        .order_by(Rating.id)
        .execution_options(stream_results=True, yield_per=resolved_batch_size)
    )
    result = await db.stream(statement)

    try:
        output = io.StringIO()
        writer = csv.writer(output)
        rows_in_chunk = 0

        async for rating, question, rater in result:
            writer.writerow(_build_export_row(rating, question, rater))
            rows_in_chunk += 1

            if rows_in_chunk >= resolved_batch_size:
                yield output.getvalue()
                output = io.StringIO()
                writer = csv.writer(output)
                rows_in_chunk = 0

        if rows_in_chunk:
            yield output.getvalue()
    finally:
        close_result = getattr(result, "close", None)
        if callable(close_result):
            maybe_awaitable = close_result()
            if hasattr(maybe_awaitable, "__await__"):
                await maybe_awaitable
