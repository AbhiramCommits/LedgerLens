import uuid
from decimal import Decimal
from typing import Any, cast

import pytest
from anthropic.types import Message, TextBlock, ToolUseBlock, Usage

from app.categorize.llm import (
    CategorizationError,
    LLMItem,
    OverrideExample,
    _build_system_prompt,
    _build_user_message,
    _parse_suggestions,
)
from app.categorize.taxonomy import Category

TRANSACTION_ID = uuid.uuid4()


def _tool_message(tool_input: object) -> Message:
    return Message(
        id="msg_test",
        content=[
            ToolUseBlock(
                id="toolu_1",
                input=cast(dict[str, Any], tool_input),
                name="categorize_transactions",
                type="tool_use",
            )
        ],
        model="claude-sonnet-4-5",
        role="assistant",
        stop_reason="tool_use",
        stop_sequence=None,
        type="message",
        usage=Usage(input_tokens=10, output_tokens=20),
    )


def _suggestion(category: str = "dining") -> dict[str, Any]:
    return {
        "transaction_id": str(uuid.uuid4()),
        "category": category,
        "confidence": 0.85,
        "reasoning": "because",
    }


def test_parses_valid_suggestions() -> None:
    entry = _suggestion()
    entry["transaction_id"] = str(TRANSACTION_ID)
    suggestions = _parse_suggestions(_tool_message({"suggestions": [entry]}))
    assert len(suggestions) == 1
    assert suggestions[0].category is Category.dining
    assert suggestions[0].confidence == 0.85
    assert suggestions[0].transaction_id == TRANSACTION_ID
    assert suggestions[0].reasoning == "because"


def test_rejects_category_outside_enum() -> None:
    good = _suggestion("dining")
    bad = _suggestion("gambling")
    suggestions = _parse_suggestions(_tool_message({"suggestions": [good, bad]}))
    assert len(suggestions) == 1
    assert suggestions[0].category is Category.dining


def test_rejects_invalid_entries_without_aborting() -> None:
    good = _suggestion("travel")
    suggestions = _parse_suggestions(
        _tool_message({"suggestions": [good, "not-an-object", {"transaction_id": "nope"}]})
    )
    assert len(suggestions) == 1
    assert suggestions[0].category is Category.travel


def test_raises_when_no_tool_call() -> None:
    message = Message(
        id="msg_test",
        content=[TextBlock(text="sorry, no tool", type="text")],
        model="claude-sonnet-4-5",
        role="assistant",
        stop_reason="end_turn",
        stop_sequence=None,
        type="message",
        usage=Usage(input_tokens=1, output_tokens=1),
    )
    with pytest.raises(CategorizationError):
        _parse_suggestions(message)


def test_raises_when_suggestions_missing() -> None:
    with pytest.raises(CategorizationError):
        _parse_suggestions(_tool_message({"other": []}))


def test_system_prompt_includes_overrides() -> None:
    system = _build_system_prompt(
        [OverrideExample(merchant_pattern="WEIRD SHOP", category="fees")]
    )
    assert "WEIRD SHOP" in system
    assert "fees" in system


def test_user_message_lists_items() -> None:
    item = LLMItem(
        transaction_id=TRANSACTION_ID,
        merchant="SHOP",
        description="stuff",
        amount=Decimal("-4.50"),
    )
    message = _build_user_message([item])
    assert "SHOP" in message
    assert "-4.50" in message
