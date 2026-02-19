from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from typing import Optional
import random
import logging

logger = logging.getLogger(__name__)

from database import get_db
from models import Experiment, Question, Rating, Rater, SESSION_DURATION_MINUTES
from schemas import (
    RaterStartResponse,
    QuestionResponse,
    RatingSubmit,
    RatingResponse,
    SessionStatusResponse,
)

router = APIRouter(prefix="/api/raters", tags=["raters"])


@router.post("/start", response_model=RaterStartResponse)
def start_session(
    experiment_id: int = Query(...),
    PROLIFIC_PID: str = Query(...),
    STUDY_ID: Optional[str] = Query(None),
    SESSION_ID: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    # Check experiment exists
    experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")

    # Check if rater already has a session for this experiment
    existing_rater = (
        db.query(Rater)
        .filter(
            Rater.prolific_id == PROLIFIC_PID,
            Rater.experiment_id == experiment_id,
        )
        .first()
    )

    if existing_rater:
        session_end = existing_rater.session_start + timedelta(
            minutes=SESSION_DURATION_MINUTES
        )

        # Check if session has expired
        if datetime.utcnow() > session_end or not existing_rater.is_active:
            raise HTTPException(
                status_code=403,
                detail="You have already completed a session for this experiment"
            )

        # Return existing active session
        return RaterStartResponse(
            rater_id=existing_rater.id,
            session_start=existing_rater.session_start,
            session_end_time=session_end,
            experiment_name=experiment.name,
            completion_url=experiment.prolific_completion_url,
        )

    # Create new rater session (store as naive UTC)
    rater = Rater(
        prolific_id=PROLIFIC_PID,
        study_id=STUDY_ID,
        session_id=SESSION_ID,
        experiment_id=experiment_id,
        session_start=datetime.utcnow(),
        is_active=True,
    )
    db.add(rater)
    db.commit()
    db.refresh(rater)
    logger.info(f"New rater session: rater_id={rater.id}, prolific_id={PROLIFIC_PID}, experiment_id={experiment_id}")

    session_end = rater.session_start + timedelta(
        minutes=SESSION_DURATION_MINUTES
    )

    return RaterStartResponse(
        rater_id=rater.id,
        session_start=rater.session_start,
        session_end_time=session_end,
        experiment_name=experiment.name,
        completion_url=experiment.prolific_completion_url,
    )


@router.get("/next-question", response_model=Optional[QuestionResponse])
def get_next_question(rater_id: int = Query(...), db: Session = Depends(get_db)):
    # Get rater and check session
    rater = db.query(Rater).filter(Rater.id == rater_id).first()
    if not rater:
        raise HTTPException(status_code=404, detail="Rater not found")

    experiment = (
        db.query(Experiment).filter(Experiment.id == rater.experiment_id).first()
    )
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")

    # Check if session expired (all times are naive UTC)
    session_end = rater.session_start + timedelta(
        minutes=SESSION_DURATION_MINUTES
    )
    if datetime.utcnow() > session_end:
        rater.is_active = False
        rater.session_end = datetime.utcnow()
        db.commit()
        raise HTTPException(status_code=403, detail="Session expired")

    # Get questions this rater has already rated
    rated_question_ids = (
        db.query(Rating.question_id).filter(Rating.rater_id == rater_id).subquery()
    )

    # Get rating counts per question
    rating_counts = (
        db.query(Question.id, func.count(Rating.id).label("count"))
        .outerjoin(Rating)
        .filter(Question.experiment_id == rater.experiment_id)
        .group_by(Question.id)
        .subquery()
    )

    # Find questions that:
    # 1. This rater hasn't rated
    # 2. Have fewer than num_ratings_per_question ratings
    eligible_questions = (
        db.query(Question, rating_counts.c.count)
        .outerjoin(rating_counts, Question.id == rating_counts.c.id)
        .filter(
            Question.experiment_id == rater.experiment_id,
            ~Question.id.in_(rated_question_ids),
        )
        .all()
    )

    # Separate into under-quota and at-quota questions
    under_quota = []
    at_quota = []

    for question, count in eligible_questions:
        count = count or 0
        if count < experiment.num_ratings_per_question:
            under_quota.append((question, count))
        else:
            at_quota.append(question)

    # Prioritize questions with fewer ratings
    if under_quota:
        # Sort by count (ascending) to prioritize questions with fewer ratings
        under_quota.sort(key=lambda x: x[1])
        # Get questions with minimum count
        min_count = under_quota[0][1]
        min_questions = [q for q, c in under_quota if c == min_count]
        selected = random.choice(min_questions)
    elif at_quota:
        # All questions have enough ratings, sample uniformly
        selected = random.choice(at_quota)
    else:
        # No more questions available for this rater
        return None

    return QuestionResponse(
        id=selected.id,
        question_id=selected.question_id,
        question_text=selected.question_text,
        options=selected.options,
        question_type=selected.question_type,
    )


@router.post("/submit", response_model=RatingResponse)
def submit_rating(rating: RatingSubmit, rater_id: int = Query(...), db: Session = Depends(get_db)):
    # Verify rater exists and is active
    rater = db.query(Rater).filter(Rater.id == rater_id).first()
    if not rater:
        raise HTTPException(status_code=404, detail="Rater not found")
    if not rater.is_active:
        raise HTTPException(status_code=403, detail="Session expired")

    # Verify question exists
    question = db.query(Question).filter(Question.id == rating.question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    # Check if rater already rated this question
    existing = (
        db.query(Rating)
        .filter(Rating.rater_id == rater_id, Rating.question_id == rating.question_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Already rated this question")

    # Validate confidence
    if rating.confidence < 1 or rating.confidence > 5:
        raise HTTPException(status_code=400, detail="Confidence must be between 1 and 5")

    # Create rating
    db_rating = Rating(
        question_id=rating.question_id,
        rater_id=rater_id,
        answer=rating.answer,
        confidence=rating.confidence,
        time_started=rating.time_started,
        time_submitted=datetime.utcnow(),
    )
    db.add(db_rating)
    db.commit()
    db.refresh(db_rating)
    logger.info(f"Rating submitted: rating_id={db_rating.id}, rater_id={rater_id}, question_id={rating.question_id}")

    return RatingResponse(id=db_rating.id, success=True)


@router.get("/session-status", response_model=SessionStatusResponse)
def get_session_status(rater_id: int = Query(...), db: Session = Depends(get_db)):
    rater = db.query(Rater).filter(Rater.id == rater_id).first()
    if not rater:
        raise HTTPException(status_code=404, detail="Rater not found")

    experiment = (
        db.query(Experiment).filter(Experiment.id == rater.experiment_id).first()
    )

    session_end = rater.session_start + timedelta(
        minutes=SESSION_DURATION_MINUTES
    )
    time_remaining = (session_end - datetime.utcnow()).total_seconds()

    if time_remaining <= 0:
        rater.is_active = False
        rater.session_end = datetime.utcnow()
        db.commit()
        time_remaining = 0

    questions_completed = (
        db.query(Rating).filter(Rating.rater_id == rater_id).count()
    )

    return SessionStatusResponse(
        is_active=rater.is_active,
        time_remaining_seconds=max(0, int(time_remaining)),
        questions_completed=questions_completed,
    )


@router.post("/end-session")
def end_session(rater_id: int = Query(...), db: Session = Depends(get_db)):
    rater = db.query(Rater).filter(Rater.id == rater_id).first()
    if not rater:
        raise HTTPException(status_code=404, detail="Rater not found")

    rater.is_active = False
    rater.session_end = datetime.utcnow()
    db.commit()

    return {"message": "Session ended successfully"}
