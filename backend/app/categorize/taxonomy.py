"""Fixed category taxonomy for transaction categorization."""

import enum


class Category(enum.StrEnum):
    groceries = "groceries"
    dining = "dining"
    transport = "transport"
    housing = "housing"
    utilities = "utilities"
    healthcare = "healthcare"
    entertainment = "entertainment"
    shopping = "shopping"
    travel = "travel"
    income = "income"
    fees = "fees"
    transfers = "transfers"
    other = "other"


CATEGORY_VALUES = tuple(category.value for category in Category)
