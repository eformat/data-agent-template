"""Reasoning rubric model — structured extraction from agent responses."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ReasoningRubric(BaseModel):
    """Structured reasoning from the 6-step protocol.

    Extracted via a second LLM call after the main answer, or parsed
    from the <reasoning> XML block in the response.
    """

    cross_dataset: str = Field(
        default="",
        description="Which dataset was used and why, alternatives considered.",
    )
    methodology: str = Field(
        default="",
        description="How the data was collected, informed interpretation.",
    )
    scope: str = Field(
        default="",
        description="Whether the question is within or outside data scope.",
    )
    causal_inference: str = Field(
        default="",
        description="Whether causal claims are appropriate.",
    )
    geographic: str = Field(
        default="",
        description="Geographic resolution analysis.",
    )
    terminology: str = Field(
        default="",
        description="Term mappings applied.",
    )


def parse_reasoning_block(text: str) -> ReasoningRubric:
    """Parse a <reasoning> block into a ReasoningRubric."""
    import re

    match = re.search(r"<reasoning>(.*?)</reasoning>", text, re.DOTALL)
    if not match:
        return ReasoningRubric()

    block = match.group(1).strip()
    fields = {}
    for line in block.split("\n"):
        line = line.strip()
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip().lower().replace(" ", "_")
            if key in ReasoningRubric.model_fields:
                fields[key] = value.strip()

    return ReasoningRubric(**fields)
