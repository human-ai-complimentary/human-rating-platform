"""OpenAI API client for generating chat responses in delegation experiments."""
from __future__ import annotations

import logging
import os

from openai import OpenAI

logger = logging.getLogger(__name__)

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set in environment")
        _client = OpenAI(api_key=api_key)
    return _client


def get_chat_response(messages: list[dict], task_question: str, task_instructions: str) -> str:
    """Get a chat response from OpenAI given conversation history and task context."""
    client = _get_client()

    system_message = (
        f"You are a helpful AI assistant helping a user answer a question.\n\n"
        f"Task Instructions: {task_instructions}\n\n"
        f"Question: {task_question}\n\n"
        f"Help the user work through this question. Be concise and helpful."
    )

    api_messages = [{"role": "system", "content": system_message}]
    for msg in messages:
        api_messages.append({"role": msg["role"], "content": msg["content"]})

    logger.debug("Sending chat request with %d messages", len(api_messages))
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=api_messages,
        max_completion_tokens=4096,
    )

    return response.choices[0].message.content or ""
