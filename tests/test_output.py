"""Tests for output cleaning and confidence card."""

from data_agent_core.agent.output import clean_output, build_confidence_card
from data_agent_core.agent.reasoning import parse_reasoning_block


def test_clean_output_strips_think():
    text = "<think>internal reasoning</think>The answer is 42."
    answer, reasoning = clean_output(text)
    assert "internal reasoning" not in answer
    assert "42" in answer


def test_clean_output_extracts_reasoning():
    text = (
        "<reasoning>\n"
        "cross_dataset: Used notifications table\n"
        "methodology: Passive surveillance\n"
        "</reasoning>\n"
        "The answer is 42."
    )
    answer, reasoning = clean_output(text)
    assert "42" in answer
    assert "cross_dataset" in reasoning
    assert "Passive surveillance" in reasoning


def test_clean_output_fixes_data_freshness():
    text = "Answer here.\n**Data Freshness**: Source | Year | Updated"
    answer, _ = clean_output(text)
    assert " | " not in answer or "Data Freshness" not in answer.split("|")[0]


def test_confidence_card_high():
    assert build_confidence_card(["query_trino", "get_methodology"]) == "HIGH"


def test_confidence_card_moderate():
    assert build_confidence_card(["query_trino"]) == "MODERATE"


def test_confidence_card_low():
    assert build_confidence_card(["describe_datasets"]) == "LOW"
    assert build_confidence_card([]) == "LOW"


def test_parse_reasoning_block():
    text = (
        "<reasoning>\n"
        "cross_dataset: Used the notifications table because it has annual counts.\n"
        "methodology: Passive surveillance via NNDSS.\n"
        "scope: Within scope — notification counts.\n"
        "causal_inference: N/A — no causal claims.\n"
        "geographic: State/territory level.\n"
        "terminology: flu mapped to influenza.\n"
        "</reasoning>"
    )
    rubric = parse_reasoning_block(text)
    assert "notifications" in rubric.cross_dataset
    assert "Passive" in rubric.methodology
    assert rubric.geographic == "State/territory level."
