from collections.abc import Sequence

from app.categorize.llm import CategorizationError, LLMItem, OverrideExample, Suggestion
from app.categorize.taxonomy import Category


class FakeCategorizer:
    """Deterministic in-memory stand-in for CategorizerClient."""

    def __init__(self) -> None:
        self.calls: list[tuple[list[str], list[str]]] = []
        self.responses: dict[str, Category] = {}
        self.fail = False

    async def categorize(
        self, items: Sequence[LLMItem], overrides: Sequence[OverrideExample]
    ) -> list[Suggestion]:
        if self.fail:
            raise CategorizationError("fake client failure")
        self.calls.append(([item.merchant for item in items], [o.category for o in overrides]))
        return [
            Suggestion(
                transaction_id=item.transaction_id,
                category=self.responses.get(item.merchant, Category.other),
                confidence=0.8,
                reasoning="fake",
            )
            for item in items
        ]
