"""Subtask decomposer for the human-as-a-tool method.

Handles all LLM calls for decomposing a question into subtasks and
synthesising a final answer. Confidence scoring is intentionally absent
here — scores are assigned by a separate ConfidenceEstimator after decomposition.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from config import get_settings

from ...llm import complete

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "openrouter/google/gemini-3.1-flash-lite-preview"

# ---------------------------------------------------------------------------
# Structured output schema
# ---------------------------------------------------------------------------

# Enforces the response shape at the API level for models that support it
# (Gemini, GPT-4o). _normalize_subtasks() remains as a backstop for models
# that don't enforce per-field enum constraints.
_RESPONSE_FORMAT: dict = {
    "type": "json_schema",
    "json_schema": {
        "name": "decomposition_response",
        "schema": {
            "type": "object",
            "properties": {
                "done": {"type": "boolean"},
                "synthesis": {
                    "type": "object",
                    "properties": {
                        "answer": {"type": "string"},
                        "reasoning": {"type": "string"},
                    },
                    "required": ["answer", "reasoning"],
                },
                "subtasks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "index": {"type": "integer"},
                            "question": {"type": "string"},
                            "my_answer": {"type": "string"},
                            "type": {
                                "type": "string",
                                "enum": ["binary", "multiple_choice", "free_text"],
                            },
                            "options": {
                                "type": ["array", "null"],
                                "items": {"type": "string"},
                            },
                        },
                        "required": ["index", "question", "my_answer", "type", "options"],
                    },
                },
            },
            "required": ["done"],
        },
    },
}

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_SUBTASK_SCHEMA = """\
Subtask schema:
{{
  "index": <integer starting at 0>,
  "question": "<atomic sub-question>",
  "type": "binary" | "multiple_choice" | "free_text",
  "options": ["opt1", "opt2", ...] | null,
  "my_answer": <see rules below>
}}

my_answer rules — follow exactly, no exceptions:
- binary:          exactly "yes" or "no" (lowercase, nothing else)
- multiple_choice: copy one option string exactly as it appears in "options", nothing else
- free_text:       a concise answer, no explanation or qualification appended

The human sees my_answer as a pre-filled response. It must be a value the UI \
can use directly — extra text will break the interface.\
"""

_START_SYSTEM = """\
Your goal is to decompose a question into all of the atomic sub-questions that \
together are sufficient to answer it — then provide your best current answer to \
each one, regardless of how confident you are.

Step 1 — Identify every specific fact, judgement, or clarification that must be \
established to answer the question. Include sub-questions you already know the \
answer to. Do not pre-filter by confidence.

Step 2 — For each sub-question, fill in "my_answer" following the schema rules \
below exactly.

You must always return subtasks — never synthesise on the first pass. \
The human must always have the opportunity to review and correct your answers.

{subtask_schema}

Respond with JSON only — no explanation, no markdown fences.

Always respond with:
{{"done": false, "subtasks": [/* up to {max_subtasks} subtask objects */]}}\
"""

_ADVANCE_SYSTEM = """\
You are working toward answering a question across multiple rounds. Each round \
you either synthesise a final answer or identify additional sub-questions still needed.

This is round {iteration} of {max_rounds} maximum.{forced_note}

The human has provided answers to your previous sub-questions. Use all of that \
information to update your understanding, then decide:

1. If you now have enough to answer the original question:
   {{"done": true, "synthesis": {{"answer": "<answer>", "reasoning": "<step-by-step explanation>"}}}}

2. If there are still sub-questions required that have not been answered:
   {{"done": false, "subtasks": [/* new subtask objects only — do not repeat already-answered ones */]}}

{subtask_schema}

Respond with JSON only — no explanation, no markdown fences.\
"""

_FORCED_NOTE = (
    " This is the final round — you MUST synthesise now regardless of remaining uncertainty."
)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class DecompositionResult:
    done: bool
    subtasks: list[dict] = field(default_factory=list)
    synthesis: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def format_history(history: list[dict]) -> str:
    lines = []
    for i, round_ in enumerate(history, 1):
        lines.append(f"Round {i}:")
        for st in round_["subtasks"]:
            human_answer = round_["answers"].get(str(st["index"]), "(no answer)")
            lines.append(f"  Uncertainty: {st['question']}")
            lines.append(f"  My answer:   {st.get('my_answer', '(none)')}")
            lines.append(f"  Human input: {human_answer}")
    return "\n".join(lines)


def _build_user_msg(question_text: str, options: str, history: list[dict] | None = None) -> str:
    msg = f"Question: {question_text}"
    if options:
        msg += f"\nAnswer options: {options}"
    if history:
        msg += f"\n\nInformation gathered so far:\n{format_history(history)}"
    return msg


def _parse_response(raw: str, context: str) -> dict:
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, AttributeError):
        logger.warning("Failed to parse %s response: %r", context, raw)
        return {}


def _normalize_subtasks(subtasks: list[dict]) -> list[dict]:
    """Enforce my_answer format per subtask type.

    The LLM sometimes appends reasoning to my_answer despite prompt instructions.
    This is the authoritative normalization — the frontend must not need to do this.

    - binary:          extract leading 'yes'/'no' word, capitalise
    - multiple_choice: find the option that my_answer starts with (case-insensitive)
    - free_text:       leave as-is
    """
    normalized = []
    for st in subtasks:
        answer = (st.get("my_answer") or "").strip()
        stype = st.get("type")

        if stype == "binary":
            lower = answer.lower()
            if lower.startswith("yes"):
                answer = "yes"
            elif lower.startswith("no"):
                answer = "no"
            else:
                logger.warning("binary my_answer %r does not start with yes/no", answer)

        elif stype == "multiple_choice":
            options: list[str] = st.get("options") or []
            lower = answer.lower()
            match = next((o for o in options if lower.startswith(o.lower())), None)
            if match:
                answer = match
            else:
                logger.warning(
                    "multiple_choice my_answer %r does not match any option %r", answer, options
                )

        normalized.append({**st, "my_answer": answer})
    return normalized


# ---------------------------------------------------------------------------
# Decomposer
# ---------------------------------------------------------------------------


class SubtaskDecomposer:
    async def start(
        self,
        question_text: str,
        options: str,
        max_subtasks: int,
        model: str | None = None,
    ) -> DecompositionResult:
        settings = get_settings()
        model = model or _DEFAULT_MODEL
        system = _START_SYSTEM.format(
            subtask_schema=_SUBTASK_SCHEMA, max_subtasks=max_subtasks
        )
        user_msg = _build_user_msg(question_text, options)

        raw = await complete(
            [{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
            model=model,
            settings=settings.llm,
            response_format=_RESPONSE_FORMAT,
        )

        parsed = _parse_response(raw, "start")
        if not parsed:
            return DecompositionResult(done=True)

        if parsed.get("done"):
            return DecompositionResult(done=True, synthesis=parsed.get("synthesis", {}))

        subtasks = _normalize_subtasks(parsed.get("subtasks", []))
        if not subtasks:
            logger.warning("start() returned done=false with no subtasks")
            return DecompositionResult(done=True)

        return DecompositionResult(done=False, subtasks=subtasks)

    async def advance(
        self,
        question_text: str,
        options: str,
        history: list[dict],
        iteration: int,
        max_rounds: int,
        model: str | None = None,
        force_synthesis: bool = False,
    ) -> DecompositionResult:
        settings = get_settings()
        model = model or _DEFAULT_MODEL
        is_final = force_synthesis or iteration >= max_rounds
        forced_note = _FORCED_NOTE if is_final else ""

        system = _ADVANCE_SYSTEM.format(
            iteration=iteration,
            max_rounds=max_rounds,
            forced_note=forced_note,
            subtask_schema=_SUBTASK_SCHEMA,
        )
        user_msg = _build_user_msg(question_text, options, history)

        raw = await complete(
            [{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
            model=model,
            settings=settings.llm,
            response_format=_RESPONSE_FORMAT,
        )

        parsed = _parse_response(raw, "advance")
        if not parsed:
            parsed = {"done": True, "synthesis": {"answer": raw, "reasoning": ""}}

        if parsed.get("done") or is_final:
            return DecompositionResult(done=True, synthesis=parsed.get("synthesis", {}))

        subtasks = _normalize_subtasks(parsed.get("subtasks", []))
        if not subtasks:
            logger.warning("advance() returned done=false with no subtasks; forcing synthesis")
            return DecompositionResult(done=True)

        return DecompositionResult(done=False, subtasks=subtasks)
