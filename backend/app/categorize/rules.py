"""Deterministic keyword/regex rules — works with zero network access."""

import re
from dataclasses import dataclass

from app.categorize.taxonomy import Category

RULE_CONFIDENCE = 0.9


@dataclass(frozen=True)
class RuleMatch:
    category: Category
    confidence: float


def _compile(*keywords: str) -> re.Pattern[str]:
    return re.compile(rf"\b(?:{'|'.join(keywords)})\b", re.IGNORECASE)


_RULES: tuple[tuple[re.Pattern[str], Category], ...] = (
    (
        _compile("payroll", "paychex", "adp", "direct deposit", "salary", "paycheck"),
        Category.income,
    ),
    (
        _compile("zelle", "venmo", "cash app", "wire transfer", "ach", "bank transfer"),
        Category.transfers,
    ),
    (
        _compile(
            "overdraft fee",
            "late fee",
            "atm fee",
            "service fee",
            "monthly fee",
            "insufficient funds",
            "returned item fee",
        ),
        Category.fees,
    ),
    (
        _compile("ubereats", "uber eats", "doordash", "grubhub", "postmates"),
        Category.dining,
    ),
    (
        _compile(
            "mcdonald",
            "starbucks",
            "chipotle",
            "domino",
            "subway",
            "taco bell",
            "dunkin",
            "kfc",
            "wendy",
            "pizza",
            "restaurant",
            "cafe",
            "coffee",
            "diner",
            "bistro",
            "sushi",
            "grill",
        ),
        Category.dining,
    ),
    (
        _compile("uber", "lyft", "taxi", "transit", "metro", "amtrak", "parking", "toll", "ezpass"),
        Category.transport,
    ),
    (
        _compile(
            "shell", "chevron", "exxon", "mobil", "sunoco", "circle k", "marathon", "speedway",
            "gas station", "fuel",
        ),
        Category.transport,
    ),
    (
        _compile(
            "whole foods", "trader joe", "safeway", "kroger", "aldi", "publix", "wegmans",
            "sprouts", "meijer", "lidl", "albertsons", "grocer",
        ),
        Category.groceries,
    ),
    (
        _compile(
            "water", "sewer", "electric", "comcast", "xfinity", "spectrum", "verizon fios",
            "utility", "internet", "power",
        ),
        Category.utilities,
    ),
    (
        _compile(
            "rent", "mortgage", "landlord", "hoa", "realty", "apartment",
            "property mgmt", "zillow",
        ),
        Category.housing,
    ),
    (
        _compile(
            "pharmacy", "cvs", "walgreens", "doctor", "medical", "dental", "hospital",
            "clinic", "health", "prescription", "optometrist",
        ),
        Category.healthcare,
    ),
    (
        _compile(
            "hilton", "marriott", "hyatt", "airbnb", "booking", "expedia", "delta air",
            "united air", "southwest", "jetblue", "american air", "hotel", "resort", "airfare",
        ),
        Category.travel,
    ),
    (
        _compile(
            "netflix", "spotify", "hulu", "disney", "hbo", "cinema", "amc", "ticketmaster",
            "concert", "steam", "playstation", "xbox", "prime video", "youtube",
        ),
        Category.entertainment,
    ),
    (
        _compile(
            "amazon", "walmart", "target", "best buy", "ikea", "home depot", "lowes",
            "macy", "nordstrom", "zara", "etsy", "ebay", "costco",
        ),
        Category.shopping,
    ),
)


def categorize_by_rule(merchant: str) -> RuleMatch | None:
    if not merchant:
        return None
    for pattern, category in _RULES:
        if pattern.search(merchant):
            return RuleMatch(category=category, confidence=RULE_CONFIDENCE)
    return None
