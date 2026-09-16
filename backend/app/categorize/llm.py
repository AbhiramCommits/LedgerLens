"""Anthropic-backed LLM categorizer behind a provider-agnostic interface.

The CategorizerClient protocol lets tests inject a fake with no network
access. The AnthropicCategorizerClient implements it with tool-use and
strict Pydantic validation of the model's JSON response.
"""

import asyncio
import logging
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol, cast

import anthropic
from anthropic.types import Message, MessageParam, ToolChoiceToolParam, ToolParam, ToolUseBlock
from pydantic import BaseModel, Field, ValidationError

from app.categorize.taxonomy import CATEGORY_VALUES, Category
from app.config import settings

logger = logging.getLogger(__name__)

_TOOL_NAME = "categorize_transactions"
MAX_ATTEMPTS = 3
BASE_BACKOFF_SECONDS = 1.0
REQUEST_TIMEOUT_SECONDS = 30.0
MAX_TOKENS = 2048

# USD per million tokens (input, output); fallback for unknown models.
_COST_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-sonnet-4-5": (3.0, 15.0),
}
_DEFAULT_COST_PER_MTOK = (3.0, 15.0)


class CategorizationError(Exception):
    """Raised when the LLM provider is unreachable or returns invalid data."""


@dataclass(frozen=True)
class LLMItem:
    transaction_id: uuid.UUID
    merchant: str
    description: str | None
    amount: Decimal


@dataclass(frozen=True)
class OverrideExample:
    merchant_pattern: str
    category: str


@dataclass(frozen=True)
class Suggestion:
    transaction_id: uuid.UUID
    category: Category
    confidence: float
    reasoning: str


class CategorizerClient(Protocol):
    async def categorize(
        self, items: Sequence[LLMItem], overrides: Sequence[OverrideExample]
    ) -> list[Suggestion]:
        """Return suggestions for the given items. May raise CategorizationError."""
        ...


class _SuggestionModel(BaseModel):
    transaction_id: uuid.UUID
    category: Category
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""


_CATEGORIZE_TOOL: dict[str, Any] = {
    "name": _TOOL_NAME,
    "description": "Assign a category to each transaction.",
    "input_schema": {
        "type": "object",
        "properties": {
            "suggestions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "transaction_id": {"type": "string"},
                        "category": {"type": "string", "enum": list(CATEGORY_VALUES)},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "reasoning": {"type": "string"},
                    },
                    "required": ["transaction_id", "category", "confidence", "reasoning"],
                },
            }
        },
        "required": ["suggestions"],
    },
}


class AnthropicCategorizerClient:
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self._api_key = api_key if api_key is not None else settings.anthropic_api_key
        self._model = model or settings.anthropic_model
        self._client: anthropic.AsyncAnthropic | None = None
        if self._api_key:
            self._client = anthropic.AsyncAnthropic(api_key=self._api_key, max_retries=0)

    async def categorize(
        self, items: Sequence[LLMItem], overrides: Sequence[OverrideExample]
    ) -> list[Suggestion]:
        if not items:
            return []
        if self._client is None:
            raise CategorizationError("anthropic_api_key is not configured")

        system = _build_system_prompt(overrides)
        user_message = _build_user_message(items)

        for attempt in range(MAX_ATTEMPTS):
            try:
                message = await self._single_call(system, user_message)
                return _parse_suggestions(message)
            except (
                anthropic.APIStatusError,
                anthropic.APIConnectionError,
                TimeoutError,
            ) as exc:
                if isinstance(exc, anthropic.APIStatusError) and not (
                    exc.status_code == 429 or exc.status_code >= 500
                ):
                    raise CategorizationError(f"anthropic api error: {exc}") from exc
                if attempt == MAX_ATTEMPTS - 1:
                    raise CategorizationError(
                        f"anthropic call failed after {MAX_ATTEMPTS} attempts: {exc}"
                    ) from exc
                delay = BASE_BACKOFF_SECONDS * (2**attempt)
                logger.warning(
                    "llm categorize retry %d/%d in %.1fs: %s",
                    attempt + 1,
                    MAX_ATTEMPTS,
                    delay,
                    exc,
                )
                await asyncio.sleep(delay)
        raise CategorizationError("anthropic call failed")  # pragma: no cover

    async def _single_call(self, system: str, user_message: str) -> Message:
        assert self._client is not None
        messages: list[MessageParam] = [{"role": "user", "content": user_message}]
        tools: list[ToolParam] = [cast(ToolParam, _CATEGORIZE_TOOL)]
        tool_choice: ToolChoiceToolParam = {"type": "tool", "name": _TOOL_NAME}
        started = time.perf_counter()
        message = await asyncio.wait_for(
            self._client.messages.create(
                model=self._model,
                max_tokens=MAX_TOKENS,
                system=system,
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
            ),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        latency = time.perf_counter() - started

        input_tokens = message.usage.input_tokens
        output_tokens = message.usage.output_tokens
        input_cost, output_cost = _COST_PER_MTOK.get(self._model, _DEFAULT_COST_PER_MTOK)
        cost = (input_tokens * input_cost + output_tokens * output_cost) / 1_000_000
        logger.info(
            "llm_categorize model=%s input_tokens=%d output_tokens=%d "
            "latency_ms=%.0f cost_usd=%.6f",
            self._model,
            input_tokens,
            output_tokens,
            latency * 1000,
            cost,
        )
        return message


def _build_system_prompt(overrides: Sequence[OverrideExample]) -> str:
    lines = [
        "You categorize personal finance transactions.",
        f"Categories (choose exactly one, lowercase): {', '.join(CATEGORY_VALUES)}.",
        "Expenses have negative amounts; income has positive amounts.",
        "Base the decision on the merchant and description.",
    ]
    if overrides:
        lines.append("The user corrected these merchants before. Prefer matching their choices:")
        for example in overrides:
            lines.append(f'- "{example.merchant_pattern}" -> {example.category}')
    return "\n".join(lines)


def _build_user_message(items: Sequence[LLMItem]) -> str:
    rows = ["id | merchant | description | amount"]
    for item in items:
        description = (item.description or "").replace("\n", " ")[:120]
        rows.append(f"{item.transaction_id} | {item.merchant} | {description} | {item.amount}")
    return "Categorize these transactions:\n" + "\n".join(rows)


def _parse_suggestions(message: Message) -> list[Suggestion]:
    tool_input = _extract_tool_input(message)
    if not isinstance(tool_input, dict):
        raise CategorizationError("llm tool input was not an object")
    entries = tool_input.get("suggestions")
    if not isinstance(entries, list):
        raise CategorizationError("llm response missing 'suggestions' list")

    suggestions: list[Suggestion] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        try:
            parsed = _SuggestionModel.model_validate(entry)
        except ValidationError:
            logger.warning("rejected invalid llm suggestion: %s", entry)
            continue
        suggestions.append(
            Suggestion(
                transaction_id=parsed.transaction_id,
                category=parsed.category,
                confidence=parsed.confidence,
                reasoning=parsed.reasoning,
            )
        )
    return suggestions


def _extract_tool_input(message: Message) -> Any:
    for block in message.content:
        if isinstance(block, ToolUseBlock) and block.name == _TOOL_NAME:
            return block.input
    raise CategorizationError("llm response contained no tool call")
