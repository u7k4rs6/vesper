"""Model output, strictly validated (§6.3). No numeric field anywhere, on purpose."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Action = Literal["SEND_INVOICE", "WAIT", "ESCALATE", "NONE"]


class Diagnosis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: Literal["soft", "hard", "pending", "unknown"]
    cause: str = Field(max_length=240)
    customer_context: str = Field(max_length=200)
    confidence: Literal["low", "medium", "high"]


class Proposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Action
    rationale: str = Field(max_length=240)
    message_template: str | None = Field(default=None, max_length=400)
    language: str = Field(pattern=r"^[a-z]{2}(-[A-Z]{2})?$")
