import asyncio
import logging
import uuid
from decimal import Decimal
from typing import Any

import anthropic
import httpx2
import pytest
from anthropic.types import Message, ToolUseBlock, Usage

from app.categorize.llm import (
    AnthropicCategorizerClient,
    CategorizationError,
    LLMItem,
    OverrideExample,
)
from app.categorize.taxonomy import Category

TRANSACTION_ID = uuid.uuid4()

ITEM = LLMItem(
    transaction_id=TRANSACTION_ID,
    merchant="OBSCURE CAFE",
    description="coffee",
    amount=Decimal("-4.50"),
)

OVERRIDE = OverrideExample(merchant_pattern="OBSCURE CAFE", category="dining")


def _tool_message(category: str = "dining") -> Message:
    return Message(
        id="msg_test",
        content=[
            ToolUseBlock(
                id="toolu_1",
                input={
                    "suggestions": [
                        {
                            "transaction_id": str(TRANSACTION_ID),
                            "category": category,
                            "confidence": 0.85,
                            "reasoning": "because",
                        }
                    ]
                },
                name="categorize_transactions",
                type="tool_use",
            )
        ],
        model="claude-sonnet-4-5",
        role="assistant",
        stop_reason="tool_use",
        stop_sequence=None,
        type="message",
        usage=Usage(input_tokens=100, output_tokens=50),
    )


class StubMessages:
    def __init__(self, responses: list[Message | Exception]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Message:
        self.calls.append(kwargs)
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _install_stub(
    monkeypatch: pytest.MonkeyPatch, responses: list[Message | Exception]
) -> StubMessages:
    messages = StubMessages(responses)

    class FactoryClient:
        def __init__(self, **_: Any) -> None:
            self.messages = messages

    monkeypatch.setattr(anthropic, "AsyncAnthropic", FactoryClient)
    return messages


def _api_status_error(status_code: int) -> anthropic.APIStatusError:
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx2.Response(status_code, request=request)
    return anthropic.APIStatusError("error", response=response, body={"error": "boom"})


def _connection_error() -> anthropic.APIConnectionError:
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return anthropic.APIConnectionError(message="connection refused", request=request)


async def test_categorize_success_and_instrumentation(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    messages = _install_stub(monkeypatch, [_tool_message()])
    client = AnthropicCategorizerClient(api_key="test-key", model="claude-sonnet-4-5")

    with caplog.at_level(logging.INFO):
        suggestions = await client.categorize([ITEM], [OVERRIDE])

    assert len(suggestions) == 1
    assert suggestions[0].transaction_id == TRANSACTION_ID
    assert suggestions[0].category is Category.dining
    assert suggestions[0].confidence == 0.85

    call = messages.calls[0]
    assert call["model"] == "claude-sonnet-4-5"
    assert call["max_tokens"] == 2048
    assert call["tool_choice"] == {"type": "tool", "name": "categorize_transactions"}
    assert "OBSCURE CAFE" in call["messages"][0]["content"]
    assert "OBSCURE CAFE" in call["system"]
    assert "dining" in call["system"]
    assert any("llm_categorize" in record.message for record in caplog.records)


async def test_missing_api_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    messages = _install_stub(monkeypatch, [])
    client = AnthropicCategorizerClient(api_key="")
    with pytest.raises(CategorizationError, match="anthropic_api_key"):
        await client.categorize([ITEM], [])
    assert messages.calls == []


async def test_retries_on_429_with_backoff(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    messages = _install_stub(
        monkeypatch, [_api_status_error(429), _api_status_error(429), _tool_message()]
    )
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    client = AnthropicCategorizerClient(api_key="test-key")

    with caplog.at_level(logging.WARNING):
        suggestions = await client.categorize([ITEM], [])

    assert len(suggestions) == 1
    assert len(messages.calls) == 3
    assert sleeps == [1.0, 2.0]
    assert any("retry" in record.message for record in caplog.records)


async def test_retries_on_5xx_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    messages = _install_stub(monkeypatch, [_api_status_error(503), _tool_message("travel")])
    client = AnthropicCategorizerClient(api_key="test-key")
    suggestions = await client.categorize([ITEM], [])
    assert len(messages.calls) == 2
    assert suggestions[0].category is Category.travel


async def test_connection_error_exhausts_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    messages = _install_stub(
        monkeypatch,
        [_connection_error(), _connection_error(), _connection_error()],
    )
    client = AnthropicCategorizerClient(api_key="test-key")
    with pytest.raises(CategorizationError, match="3 attempts"):
        await client.categorize([ITEM], [])
    assert len(messages.calls) == 3


async def test_timeout_exhausts_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    messages = _install_stub(monkeypatch, [TimeoutError(), TimeoutError(), TimeoutError()])
    client = AnthropicCategorizerClient(api_key="test-key")
    with pytest.raises(CategorizationError, match="3 attempts"):
        await client.categorize([ITEM], [])
    assert len(messages.calls) == 3


async def test_non_retryable_status_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    messages = _install_stub(monkeypatch, [_api_status_error(400)])
    client = AnthropicCategorizerClient(api_key="test-key")
    with pytest.raises(CategorizationError, match="anthropic api error"):
        await client.categorize([ITEM], [])
    assert len(messages.calls) == 1


async def test_empty_items_short_circuits(monkeypatch: pytest.MonkeyPatch) -> None:
    messages = _install_stub(monkeypatch, [])
    client = AnthropicCategorizerClient(api_key="test-key")
    assert await client.categorize([], []) == []
    assert messages.calls == []
