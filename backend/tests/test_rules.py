import pytest

from app.categorize.rules import categorize_by_rule
from app.categorize.taxonomy import Category


@pytest.mark.parametrize(
    ("merchant", "expected"),
    [
        ("STARBUCKS", Category.dining),
        ("UBEREATS", Category.dining),
        ("UBER", Category.transport),
        ("SHELL OIL", Category.transport),
        ("WHOLE FOODS", Category.groceries),
        ("PAYROLL ACME CORP", Category.income),
        ("ZELLE TO JOHN", Category.transfers),
        ("MONTHLY SERVICE FEE", Category.fees),
        ("NETFLIX", Category.entertainment),
        ("HILTON HOTEL", Category.travel),
        ("CVS PHARMACY", Category.healthcare),
        ("APARTMENT RENT", Category.housing),
        ("COMCAST", Category.utilities),
        ("AMAZON", Category.shopping),
        ("RANDOM MERCHANT", None),
        ("", None),
    ],
)
def test_categorize_by_rule(merchant: str, expected: Category | None) -> None:
    match = categorize_by_rule(merchant)
    assert (match.category if match else None) == expected
    if match:
        assert match.confidence == 0.9


def test_case_insensitive() -> None:
    match = categorize_by_rule("amazon prime")
    assert match is not None
    assert match.category is Category.shopping
