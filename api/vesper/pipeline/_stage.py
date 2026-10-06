"""Shared plumbing for the two model stages: prompt loading and validate-with-one-retry."""

from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError

PROMPTS = Path(__file__).resolve().parents[2] / "prompts"

M = TypeVar("M", bound=BaseModel)


class StageFailed(Exception):
    """The stage could not produce a valid answer. `reason` is the timeline sentence."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def load_prompt(name: str) -> str:
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8")


def validate_twice(call, model: type[M], user: str) -> M:
    """`call(user_text) -> raw JSON`. On a validation failure, retry once with the error appended."""
    raw = call(user)
    try:
        return model.model_validate_json(raw)
    except ValidationError as first:
        retry = f"{user}\n\nYour previous answer was rejected: {first.errors(include_url=False, include_input=False)}. Answer again, fixing that."
        try:
            return model.model_validate_json(call(retry))
        except ValidationError:
            raise StageFailed("The model's answer could not be validated twice.") from None
