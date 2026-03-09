from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from config import ProlificMode
from models import ProlificStudyStatus


# Prolific schemas
class ProlificStudyConfig(BaseModel):
    description: str
    estimated_completion_time: int = Field(ge=1)
    reward: int = Field(ge=1)
    total_available_places: int = Field(ge=1)
    device_compatibility: list[Literal["desktop", "tablet", "mobile"]] = Field(
        default_factory=lambda: ["desktop"]
    )


class PilotStudyCreate(BaseModel):
    description: str
    estimated_completion_time: int = Field(ge=1)
    reward: int = Field(ge=1)
    pilot_hours: int = Field(default=5, ge=1)
    device_compatibility: list[Literal["desktop", "tablet", "mobile"]] = Field(
        default_factory=lambda: ["desktop"]
    )


class StudyRoundCreate(BaseModel):
    places: int = Field(ge=1)


class RecommendationResponse(BaseModel):
    avg_time_per_question_seconds: float
    remaining_rating_actions: int
    total_hours_remaining: float
    recommended_places: int
    is_complete: bool


class StudyRoundResponse(BaseModel):
    id: int
    round_number: int
    is_pilot: bool
    prolific_study_id: str
    prolific_study_status: ProlificStudyStatus
    places_requested: int
    created_at: datetime
    prolific_study_url: str

    model_config = ConfigDict(from_attributes=True)


class PlatformStatus(BaseModel):
    prolific_enabled: bool
    prolific_mode: ProlificMode


class FakeStudyDetailResponse(BaseModel):
    study_id: str
    study_status: ProlificStudyStatus
    experiment_id: int
    experiment_name: str
    round_number: int
    is_pilot: bool
    places_requested: int
    description: str
    estimated_completion_time: int
    reward: int
    device_compatibility: list[Literal["desktop", "tablet", "mobile"]]
    external_study_url: str
    completion_url: Optional[str] = None
    created_at: datetime


# Experiment schemas
class ExperimentCreate(BaseModel):
    name: str
    num_ratings_per_question: int = 3
    prolific_completion_url: Optional[str] = None
    prolific: Optional[ProlificStudyConfig] = None


class ExperimentResponse(BaseModel):
    id: int
    name: str
    created_at: datetime
    num_ratings_per_question: int
    prolific_completion_url: Optional[str] = None
    prolific_study_id: Optional[str] = None
    prolific_study_status: Optional[ProlificStudyStatus] = None
    prolific_study_url: Optional[str] = None
    question_count: int = 0
    rating_count: int = 0

    model_config = ConfigDict(from_attributes=True)


# Question schemas
class QuestionResponse(BaseModel):
    id: int
    question_id: str
    question_text: str
    options: Optional[str] = None
    question_type: str

    model_config = ConfigDict(from_attributes=True)


# Rater schemas
class RaterStartResponse(BaseModel):
    rater_id: int
    session_start: datetime
    session_end_time: datetime
    experiment_name: str
    completion_url: Optional[str] = None


class SessionStatusResponse(BaseModel):
    is_active: bool
    time_remaining_seconds: int
    questions_completed: int


# Rating schemas
class RatingSubmit(BaseModel):
    question_id: int
    answer: str
    confidence: int = Field(ge=1, le=5)
    time_started: datetime


class RatingResponse(BaseModel):
    id: int
    success: bool
