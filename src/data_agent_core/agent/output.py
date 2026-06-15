"""Output cleaning and confidence card generation."""

from __future__ import annotations

import re


def clean_output(text: str) -> tuple[str, str]:
    """Strip XML tags and extract reasoning block.

    Returns (answer, reasoning) tuple.
    """
    # Strip <think>...</think>
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"</?think>", "", text)
    last = text.rfind("</think>")
    if last != -1:
        text = text[last + 8:]

    # Extract <reasoning> block
    reasoning = ""
    match = re.search(r"<reasoning>(.*?)</reasoning>", text, re.DOTALL)
    if match:
        reasoning = match.group(1).strip()
        text = text[: match.start()] + text[match.end():]

    # Format reasoning as bullet points
    if reasoning:
        lines = []
        for line in reasoning.split("\n"):
            line = line.strip()
            if not line:
                continue
            if ":" in line:
                key, _, value = line.partition(":")
                lines.append(f"- **{key.strip()}:** {value.strip()}")
            else:
                lines.append(f"- {line}")
        reasoning = "\n".join(lines)

    output = text.strip()

    # Fix Data Freshness — pipe | characters cause Chainlit's markdown
    # parser to interpret the line as a table header.
    fixed_lines = []
    for line in output.split("\n"):
        if "Data Freshness" in line:
            line = line.lstrip("#").strip()
            line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)
            line = line.replace(" | ", " · ")
        fixed_lines.append(line)
    output = "\n".join(fixed_lines)

    return output, reasoning


def build_confidence_card(tool_names: list[str]) -> str:
    """Deterministic confidence level from tool trace.

    HIGH: query_trino + get_methodology both called
    MODERATE: query_trino called (data retrieved, no methodology context)
    LOW: no data tools called
    """
    has_query = "query_trino" in tool_names
    has_methodology = "get_methodology" in tool_names

    if has_query and has_methodology:
        return "HIGH"
    elif has_query:
        return "MODERATE"
    else:
        return "LOW"
