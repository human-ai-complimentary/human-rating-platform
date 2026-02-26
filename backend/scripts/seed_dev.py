from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import func
from sqlmodel import Session, create_engine, select

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config import get_settings  # noqa: E402
from models import Experiment, Question  # noqa: E402


def _to_optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def main() -> int:
    settings = get_settings()

    if not settings.seeding.enabled:
        print("Skipping seed run because [seeding].enabled is false.")
        return 0

    engine = create_engine(settings.sync_database_url, pool_pre_ping=True)

    with Session(engine) as session:
        experiment = session.exec(
            select(Experiment)
            .where(Experiment.name == settings.seeding.experiment_name)
            .order_by(Experiment.id)
        ).first()

        if experiment is None:
            experiment = Experiment(
                name=settings.seeding.experiment_name,
                num_ratings_per_question=settings.seeding.num_ratings_per_question,
                prolific_completion_url=_to_optional(settings.seeding.prolific_completion_url),
            )
            session.add(experiment)
            session.commit()
            session.refresh(experiment)
            print(
                "Created seed experiment "
                f"id={experiment.id} name={settings.seeding.experiment_name!r}"
            )

        existing_count = session.exec(
            select(func.count())
            .select_from(Question)
            .where(Question.experiment_id == experiment.id)
        ).one()

        if existing_count >= settings.seeding.question_count:
            print(
                "Seed already satisfies configured question count "
                f"({existing_count}/{settings.seeding.question_count})."
            )
            return 0

        for index in range(existing_count + 1, settings.seeding.question_count + 1):
            session.add(
                Question(
                    experiment_id=experiment.id,
                    question_id=f"seed-{index}",
                    question_text=f"Seed question {index}",
                    gt_answer="",
                    options="Yes|No",
                    question_type="MC",
                    extra_data="{}",
                )
            )

        session.commit()
        print(
            "Seeded questions to target count "
            f"{settings.seeding.question_count} for experiment_id={experiment.id}."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
