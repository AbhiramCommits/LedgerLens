"""Three-tier categorization pipeline: user overrides -> rules -> LLM.

The pipeline never raises on LLM/provider failures — it logs the reason,
falls back to the rule tier, and finally to `other` so an import (or any
caller) can never crash because of categorization.
"""

import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.categorize.llm import CategorizerClient, LLMItem, OverrideExample, Suggestion
from app.categorize.rules import RULE_CONFIDENCE, categorize_by_rule
from app.categorize.taxonomy import Category
from app.models import Account, CategoryOverride, CategorySource, Transaction

logger = logging.getLogger(__name__)

LLM_BATCH_SIZE = 25
FEW_SHOT_LIMIT = 10
OVERRIDE_CONFIDENCE = 1.0
FALLBACK_CONFIDENCE = 0.0


@dataclass
class CategorizeResult:
    categorized: int = 0
    by_source: dict[str, int] = field(
        default_factory=lambda: {"user": 0, "rule": 0, "llm": 0, "fallback": 0}
    )
    fallback_reasons: list[str] = field(default_factory=list)
    transactions: list[Transaction] = field(default_factory=list)


async def run_categorization(
    session: AsyncSession,
    user_id: uuid.UUID,
    client: CategorizerClient,
) -> CategorizeResult:
    result = CategorizeResult()

    stmt = (
        select(Transaction)
        .join(Account, Transaction.account_id == Account.id)
        .where(Account.user_id == user_id, Transaction.category.is_(None))
        .order_by(Transaction.id)
    )
    transactions = list((await session.scalars(stmt)).all())
    if not transactions:
        return result

    overrides = list(
        (
            await session.scalars(
                select(CategoryOverride)
                .where(CategoryOverride.user_id == user_id)
                .order_by(CategoryOverride.created_at.desc())
            )
        ).all()
    )
    few_shot = [
        OverrideExample(merchant_pattern=override.merchant_pattern, category=override.category)
        for override in overrides[:FEW_SHOT_LIMIT]
    ]

    llm_queue: list[Transaction] = []
    for transaction in transactions:
        override_category = _match_override(transaction.merchant_raw, overrides)
        if override_category is not None:
            _assign(transaction, override_category, CategorySource.user, OVERRIDE_CONFIDENCE)
            result.by_source["user"] += 1
            continue

        rule = categorize_by_rule(transaction.merchant_raw)
        if rule is not None:
            _assign(transaction, rule.category.value, CategorySource.rule, RULE_CONFIDENCE)
            result.by_source["rule"] += 1
            continue

        llm_queue.append(transaction)

    for start in range(0, len(llm_queue), LLM_BATCH_SIZE):
        chunk = llm_queue[start : start + LLM_BATCH_SIZE]
        unique: dict[str, Transaction] = {}
        for transaction in chunk:
            unique.setdefault(transaction.merchant_raw, transaction)

        items = [
            LLMItem(
                transaction_id=transaction.id,
                merchant=transaction.merchant_raw,
                description=transaction.description,
                amount=transaction.amount,
            )
            for transaction in unique.values()
        ]

        try:
            suggestions = await client.categorize(items, few_shot)
        except Exception as exc:
            logger.warning("llm categorization failed, falling back: %s", exc)
            reason = f"llm failure: {exc}"
            if reason not in result.fallback_reasons:
                result.fallback_reasons.append(reason)
            suggestions = []

        by_merchant: dict[str, Suggestion] = {}
        for transaction in unique.values():
            suggestion = next(
                (s for s in suggestions if s.transaction_id == transaction.id), None
            )
            if suggestion is not None:
                by_merchant[transaction.merchant_raw] = suggestion

        missing = 0
        for transaction in chunk:
            suggestion = by_merchant.get(transaction.merchant_raw)
            if suggestion is not None:
                _assign(
                    transaction,
                    suggestion.category.value,
                    CategorySource.llm,
                    suggestion.confidence,
                )
                result.by_source["llm"] += 1
            else:
                missing += 1
                rule = categorize_by_rule(transaction.merchant_raw)
                if rule is not None:
                    _assign(transaction, rule.category.value, CategorySource.rule, RULE_CONFIDENCE)
                    result.by_source["rule"] += 1
                else:
                    _assign(
                        transaction,
                        Category.other.value,
                        CategorySource.rule,
                        FALLBACK_CONFIDENCE,
                    )
                    result.by_source["fallback"] += 1

        if missing and "llm returned no valid suggestion for some transactions" not in (
            result.fallback_reasons
        ):
            result.fallback_reasons.append(
                "llm returned no valid suggestion for some transactions"
            )

    await session.commit()

    result.categorized = sum(result.by_source.values())
    result.transactions = [transaction for transaction in transactions if transaction.category]
    return result


def _assign(
    transaction: Transaction, category: str, source: CategorySource, confidence: float
) -> None:
    transaction.category = category
    transaction.category_source = source
    transaction.confidence = confidence


def _match_override(
    merchant: str, overrides: Sequence[CategoryOverride]
) -> str | None:
    if not merchant:
        return None
    merchant_folded = merchant.casefold()
    for override in overrides:
        if override.merchant_pattern and override.merchant_pattern.casefold() in merchant_folded:
            return override.category
    return None
