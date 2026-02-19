from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
import csv
import io
import json
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

from database import get_db
from models import Experiment, Question, Rating, Rater, Upload
from schemas import ExperimentCreate, ExperimentResponse

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/experiments", response_model=ExperimentResponse)
def create_experiment(experiment: ExperimentCreate, db: Session = Depends(get_db)):
    db_experiment = Experiment(
        name=experiment.name,
        num_ratings_per_question=experiment.num_ratings_per_question,
        prolific_completion_url=experiment.prolific_completion_url,
    )
    db.add(db_experiment)
    db.commit()
    db.refresh(db_experiment)
    logger.info(f"Created experiment: id={db_experiment.id}, name={db_experiment.name}")
    return ExperimentResponse(
        id=db_experiment.id,
        name=db_experiment.name,
        created_at=db_experiment.created_at,
        num_ratings_per_question=db_experiment.num_ratings_per_question,
        prolific_completion_url=db_experiment.prolific_completion_url,
        question_count=0,
        rating_count=0,
    )


@router.get("/experiments", response_model=List[ExperimentResponse])
def list_experiments(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    # Subquery for question counts per experiment
    question_counts = (
        db.query(
            Question.experiment_id,
            func.count(Question.id).label("question_count")
        )
        .group_by(Question.experiment_id)
        .subquery()
    )

    # Subquery for rating counts per experiment
    rating_counts = (
        db.query(
            Question.experiment_id,
            func.count(Rating.id).label("rating_count")
        )
        .join(Rating, Rating.question_id == Question.id)
        .group_by(Question.experiment_id)
        .subquery()
    )

    # Single query with left joins to get all data
    experiments = (
        db.query(
            Experiment,
            func.coalesce(question_counts.c.question_count, 0).label("question_count"),
            func.coalesce(rating_counts.c.rating_count, 0).label("rating_count"),
        )
        .outerjoin(question_counts, Experiment.id == question_counts.c.experiment_id)
        .outerjoin(rating_counts, Experiment.id == rating_counts.c.experiment_id)
        .order_by(Experiment.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return [
        ExperimentResponse(
            id=exp.id,
            name=exp.name,
            created_at=exp.created_at,
            num_ratings_per_question=exp.num_ratings_per_question,
            prolific_completion_url=exp.prolific_completion_url,
            question_count=question_count,
            rating_count=rating_count,
        )
        for exp, question_count, rating_count in experiments
    ]


MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


@router.post("/experiments/{experiment_id}/upload")
def upload_questions(
    experiment_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)
):
    experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")

    # Validate file type
    if not file.filename or not file.filename.lower().endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV file")

    # Read and validate file size
    content_bytes = file.file.read()
    if len(content_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File size exceeds 50MB limit")

    try:
        content = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded")
    reader = csv.DictReader(io.StringIO(content))

    questions_added = 0
    required_fields = ["question_id", "question_text"]

    for row in reader:
        # Validate required fields
        for field in required_fields:
            if field not in row:
                raise HTTPException(
                    status_code=400, detail=f"Missing required field: {field}"
                )

        question = Question(
            experiment_id=experiment_id,
            question_id=row["question_id"],
            question_text=row["question_text"],
            gt_answer=row.get("gt_answer", ""),
            options=row.get("options", ""),
            question_type=row.get("question_type", "MC"),
            extra_data=row.get("metadata", "{}"),
        )
        db.add(question)
        questions_added += 1

    # Record the upload
    upload = Upload(
        experiment_id=experiment_id,
        filename=file.filename,
        question_count=questions_added,
    )
    db.add(upload)
    db.commit()
    logger.info(f"Uploaded {questions_added} questions to experiment {experiment_id} from {file.filename}")
    return {"message": f"Uploaded {questions_added} questions"}


@router.get("/experiments/{experiment_id}/uploads")
def list_uploads(
    experiment_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")

    uploads = (
        db.query(Upload)
        .filter(Upload.experiment_id == experiment_id)
        .order_by(Upload.uploaded_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return [
        {
            "id": u.id,
            "filename": u.filename,
            "uploaded_at": u.uploaded_at.isoformat(),
            "question_count": u.question_count,
        }
        for u in uploads
    ]


@router.get("/experiments/{experiment_id}/export")
def export_ratings(experiment_id: int, db: Session = Depends(get_db)):
    experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")

    def generate_csv():
        # Write header
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
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
        )
        yield output.getvalue()

        # Stream ratings in batches
        batch_size = 1000
        offset = 0

        while True:
            ratings = (
                db.query(Rating, Question, Rater)
                .join(Question, Rating.question_id == Question.id)
                .join(Rater, Rating.rater_id == Rater.id)
                .filter(Question.experiment_id == experiment_id)
                .offset(offset)
                .limit(batch_size)
                .all()
            )

            if not ratings:
                break

            output = io.StringIO()
            writer = csv.writer(output)

            for rating, question, rater in ratings:
                response_time = (rating.time_submitted - rating.time_started).total_seconds()
                writer.writerow(
                    [
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
                )

            yield output.getvalue()
            offset += batch_size

    return StreamingResponse(
        generate_csv(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=experiment_{experiment_id}_ratings.csv"
        },
    )


@router.delete("/experiments/{experiment_id}")
def delete_experiment(experiment_id: int, db: Session = Depends(get_db)):
    experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")

    # With CASCADE delete constraints, we just need to delete the experiment
    experiment_name = experiment.name
    db.delete(experiment)
    db.commit()
    logger.info(f"Deleted experiment: id={experiment_id}, name={experiment_name}")

    return {"message": "Experiment deleted successfully"}


@router.get("/experiments/{experiment_id}/stats")
def get_experiment_stats(experiment_id: int, db: Session = Depends(get_db)):
    experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")

    total_questions = (
        db.query(Question).filter(Question.experiment_id == experiment_id).count()
    )
    total_ratings = (
        db.query(Rating)
        .join(Question)
        .filter(Question.experiment_id == experiment_id)
        .count()
    )
    total_raters = (
        db.query(Rater).filter(Rater.experiment_id == experiment_id).count()
    )

    # Questions with enough ratings
    questions_complete = (
        db.query(Question)
        .filter(Question.experiment_id == experiment_id)
        .join(Rating)
        .group_by(Question.id)
        .having(func.count(Rating.id) >= experiment.num_ratings_per_question)
        .count()
    )

    return {
        "experiment_name": experiment.name,
        "total_questions": total_questions,
        "questions_complete": questions_complete,
        "total_ratings": total_ratings,
        "total_raters": total_raters,
        "target_ratings_per_question": experiment.num_ratings_per_question,
    }


@router.get("/experiments/{experiment_id}/analytics")
def get_experiment_analytics(experiment_id: int, db: Session = Depends(get_db)):
    experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")

    # Get all ratings with their questions and raters
    ratings = (
        db.query(Rating, Question, Rater)
        .join(Question, Rating.question_id == Question.id)
        .join(Rater, Rating.rater_id == Rater.id)
        .filter(Question.experiment_id == experiment_id)
        .all()
    )

    if not ratings:
        return {
            "experiment_name": experiment.name,
            "overview": {
                "total_ratings": 0,
                "total_questions": db.query(Question).filter(Question.experiment_id == experiment_id).count(),
                "total_raters": 0,
                "avg_response_time_seconds": 0,
                "avg_confidence": 0,
            },
            "questions": [],
            "raters": [],
        }

    # Calculate response times
    response_times = []
    confidences = []
    question_stats = {}
    rater_stats = {}

    for rating, question, rater in ratings:
        response_time = (rating.time_submitted - rating.time_started).total_seconds()
        response_times.append(response_time)
        confidences.append(rating.confidence)

        # Per-question stats
        q_id = question.question_id
        if q_id not in question_stats:
            question_stats[q_id] = {
                "question_id": q_id,
                "question_text": question.question_text[:100] + "..." if len(question.question_text) > 100 else question.question_text,
                "num_ratings": 0,
                "response_times": [],
                "confidences": [],
                "answers": [],
            }
        question_stats[q_id]["num_ratings"] += 1
        question_stats[q_id]["response_times"].append(response_time)
        question_stats[q_id]["confidences"].append(rating.confidence)
        question_stats[q_id]["answers"].append(rating.answer)

        # Per-rater stats
        r_id = rater.prolific_id
        if r_id not in rater_stats:
            rater_stats[r_id] = {
                "prolific_id": r_id,
                "study_id": rater.study_id,
                "session_start": rater.session_start.isoformat() if rater.session_start else None,
                "session_end": rater.session_end.isoformat() if rater.session_end else None,
                "is_active": rater.is_active,
                "num_ratings": 0,
                "response_times": [],
                "confidences": [],
            }
        rater_stats[r_id]["num_ratings"] += 1
        rater_stats[r_id]["response_times"].append(response_time)
        rater_stats[r_id]["confidences"].append(rating.confidence)

    # Compute final question stats
    questions_list = []
    for q_id, stats in question_stats.items():
        # Count answer distribution for MC questions
        answer_counts = {}
        for ans in stats["answers"]:
            answer_counts[ans] = answer_counts.get(ans, 0) + 1

        questions_list.append({
            "question_id": stats["question_id"],
            "question_text": stats["question_text"],
            "num_ratings": stats["num_ratings"],
            "avg_response_time_seconds": round(sum(stats["response_times"]) / len(stats["response_times"]), 2),
            "min_response_time_seconds": round(min(stats["response_times"]), 2),
            "max_response_time_seconds": round(max(stats["response_times"]), 2),
            "avg_confidence": round(sum(stats["confidences"]) / len(stats["confidences"]), 2),
            "answer_distribution": answer_counts,
        })

    # Compute final rater stats
    raters_list = []
    for r_id, stats in rater_stats.items():
        total_time = sum(stats["response_times"])
        raters_list.append({
            "prolific_id": stats["prolific_id"],
            "study_id": stats["study_id"],
            "session_start": stats["session_start"],
            "session_end": stats["session_end"],
            "is_active": stats["is_active"],
            "num_ratings": stats["num_ratings"],
            "total_response_time_seconds": round(total_time, 2),
            "avg_response_time_seconds": round(total_time / stats["num_ratings"], 2),
            "avg_confidence": round(sum(stats["confidences"]) / len(stats["confidences"]), 2),
        })

    # Sort raters by number of ratings (descending)
    raters_list.sort(key=lambda x: x["num_ratings"], reverse=True)

    return {
        "experiment_name": experiment.name,
        "overview": {
            "total_ratings": len(ratings),
            "total_questions": db.query(Question).filter(Question.experiment_id == experiment_id).count(),
            "total_raters": len(rater_stats),
            "avg_response_time_seconds": round(sum(response_times) / len(response_times), 2),
            "min_response_time_seconds": round(min(response_times), 2),
            "max_response_time_seconds": round(max(response_times), 2),
            "avg_confidence": round(sum(confidences) / len(confidences), 2),
        },
        "questions": questions_list,
        "raters": raters_list,
    }
