from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session
from schemas import (
    QuestionResponse,
    RaterStartResponse,
    RatingResponse,
    RatingSubmit,
    SessionStatusResponse,
)
from services import rater

router = APIRouter(prefix="/raters", tags=["raters"])


@router.post("/start", response_model=RaterStartResponse)
async def start_session(
    experiment_id: int = Query(...),
    PROLIFIC_PID: str = Query(...),
    STUDY_ID: Optional[str] = Query(None),
    SESSION_ID: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_session),
):
    return await rater.start_session(
        experiment_id=experiment_id,
        prolific_pid=PROLIFIC_PID,
        study_id=STUDY_ID,
        session_id=SESSION_ID,
        db=db,
    )


@router.get("/next-question", response_model=Optional[QuestionResponse])
async def get_next_question(
    rater_id: int = Query(...),
    db: AsyncSession = Depends(get_session),
):
    return await rater.get_next_question(rater_id=rater_id, db=db)


@router.post("/submit", response_model=RatingResponse)
async def submit_rating(
    rating: RatingSubmit,
    rater_id: int = Query(...),
    db: AsyncSession = Depends(get_session),
):
    return await rater.submit_rating(payload=rating, rater_id=rater_id, db=db)


@router.get("/session-status", response_model=SessionStatusResponse)
async def get_session_status(
    rater_id: int = Query(...),
    db: AsyncSession = Depends(get_session),
):
    return await rater.get_session_status(rater_id=rater_id, db=db)


@router.post("/end-session")
async def end_session(
    rater_id: int = Query(...),
    db: AsyncSession = Depends(get_session),
):
    return await rater.end_session(rater_id=rater_id, db=db)
