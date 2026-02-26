from __future__ import annotations

import random

from models import Question


def build_question_selection_groups(
    *,
    eligible_questions: list[tuple[Question, int | None]],
    target_ratings_per_question: int,
) -> tuple[list[tuple[Question, int]], list[Question]]:
    under_quota: list[tuple[Question, int]] = []
    at_quota: list[Question] = []

    for question, count in eligible_questions:
        rating_count = int(count or 0)
        if rating_count < target_ratings_per_question:
            under_quota.append((question, rating_count))
        else:
            at_quota.append(question)

    return under_quota, at_quota


def build_selected_question(
    *,
    under_quota: list[tuple[Question, int]],
    at_quota: list[Question],
) -> Question | None:
    # Prioritize the least-rated questions first to keep experiment coverage balanced.
    if under_quota:
        under_quota.sort(key=lambda item: item[1])
        min_count = under_quota[0][1]
        min_questions = [question for question, count in under_quota if count == min_count]
        return random.choice(min_questions)

    if at_quota:
        return random.choice(at_quota)

    return None
