"""Pure, dependency-free CSV parsing for bank transaction files.

This module performs no database access and only uses the standard library,
so it can be unit-tested in isolation. It takes raw CSV bytes and returns
parsed rows with normalized dates, signed amounts, and cleaned merchants.
"""

import csv
import io
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

QUANTIZED = Decimal("0.01")

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y%m%d",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%m/%d/%Y",
    "%m-%d-%Y",
    "%m/%d/%y",
    "%m-%d-%y",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d/%m/%y",
    "%d-%m-%y",
    "%b %d, %Y",
    "%d %b %Y",
    "%d-%b-%Y",
    "%b %d %Y",
)

_CURRENCY_CODES = (
    "USD",
    "CAD",
    "EUR",
    "GBP",
    "AUD",
    "NZD",
    "INR",
    "JPY",
    "CNY",
    "CHF",
    "MXN",
    "BRL",
    "SEK",
    "NOK",
    "DKK",
    "PLN",
    "ZAR",
    "HKD",
    "SGD",
)
_CURRENCY_SYMBOLS = ("$", "€", "£", "¥", "₹", "₩")

_PROCESSOR_PREFIXES = (
    "SQ *",
    "SQ*",
    "TST*",
    "TST *",
    "INTUIT*",
    "INTUIT *",
    "PAYPAL *",
    "PYPL *",
    "PP*",
    "PP *",
    "SP *",
)

_US_STATES = (
    "AL",
    "AK",
    "AZ",
    "AR",
    "CA",
    "CO",
    "CT",
    "DE",
    "DC",
    "FL",
    "GA",
    "HI",
    "ID",
    "IL",
    "IN",
    "IA",
    "KS",
    "KY",
    "LA",
    "ME",
    "MD",
    "MA",
    "MI",
    "MN",
    "MS",
    "MO",
    "MT",
    "NE",
    "NV",
    "NH",
    "NJ",
    "NM",
    "NY",
    "NC",
    "ND",
    "OH",
    "OK",
    "OR",
    "PA",
    "RI",
    "SC",
    "SD",
    "TN",
    "TX",
    "UT",
    "VT",
    "VA",
    "WA",
    "WV",
    "WI",
    "WY",
)

_STATE_SUFFIX = re.compile(rf"\s+({'|'.join(_US_STATES)})\s*$")
_TRAILING_STORE_NUMBER = re.compile(r"\s*#?\d{1,6}\s*$")
_LONG_DIGIT_RUN = re.compile(r"\s*\d{7,}")
_WHITESPACE_RUN = re.compile(r"\s+")
_DEBIT_SUFFIX = re.compile(r"^(.*?)\s*(DR|CR)$", re.IGNORECASE)

_DATE_HINTS = ("date", "posted")
_DESCRIPTION_HINTS = (
    "description",
    "memo",
    "payee",
    "merchant",
    "narrative",
    "details",
    "name",
)
_DEBIT_HINTS = ("debit", "withdrawal", "money out", "paid out")
_CREDIT_HINTS = ("credit", "deposit", "money in", "paid in")
_AMOUNT_HINTS = ("amount",)


class ColumnMappingError(ValueError):
    """Raised when the CSV header row cannot be mapped to known columns."""


@dataclass(frozen=True)
class ColumnMapping:
    date: int
    description: int | None
    amount: int | None
    debit: int | None
    credit: int | None


@dataclass(frozen=True)
class ParsedRow:
    row_number: int
    posted_date: date
    description: str | None
    merchant_raw: str
    amount: Decimal


@dataclass(frozen=True)
class ParseError:
    row_number: int
    reason: str


@dataclass(frozen=True)
class ParseResult:
    rows: list[ParsedRow]
    errors: list[ParseError]


def parse_csv(data: bytes) -> ParseResult:
    """Parse CSV bytes into normalized rows and per-row errors.

    Raises ColumnMappingError if the file is empty or the header cannot be
    mapped to recognizable columns. Individual bad rows are reported as
    ParseError entries instead of aborting the parse.
    """
    if not data:
        raise ColumnMappingError("file is empty")

    text = _decode(data)
    delimiter = _detect_delimiter(text)
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)
    try:
        header = next(reader)
    except StopIteration:
        raise ColumnMappingError("file is empty") from None

    mapping = detect_column_mapping(_clean_headers(header))

    rows: list[ParsedRow] = []
    errors: list[ParseError] = []
    for row_number, raw in enumerate(reader, start=2):
        cells = [cell.strip() for cell in raw]
        if not any(cells):
            continue
        parsed = _parse_row(cells, mapping, row_number)
        if isinstance(parsed, ParseError):
            errors.append(parsed)
        else:
            rows.append(parsed)

    return ParseResult(rows=rows, errors=errors)


def detect_column_mapping(headers: list[str]) -> ColumnMapping:
    """Resolve header names to column indexes using keyword heuristics."""
    normalized = [header.strip().lower() for header in headers]

    def find(hints: tuple[str, ...], exclude: tuple[str, ...] = ()) -> int | None:
        for index, header in enumerate(normalized):
            if any(hint in header for hint in hints) and not any(
                word in header for word in exclude
            ):
                return index
        return None

    date_idx = find(_DATE_HINTS)
    if date_idx is None:
        raise ColumnMappingError("no date column found in header")

    debit_idx = find(_DEBIT_HINTS)
    credit_idx = find(_CREDIT_HINTS)
    amount_idx = find(_AMOUNT_HINTS, exclude=("debit", "credit"))
    description_idx = find(_DESCRIPTION_HINTS)

    if debit_idx is None and credit_idx is None and amount_idx is None:
        raise ColumnMappingError("no amount column found in header")

    return ColumnMapping(
        date=date_idx,
        description=description_idx,
        amount=amount_idx,
        debit=debit_idx,
        credit=credit_idx,
    )


def parse_date(text: str) -> date | None:
    """Parse a date string across several common bank CSV formats."""
    text = text.strip()
    if not text:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    first_token = re.split(r"[\sT]", text, maxsplit=1)[0]
    if first_token != text:
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(first_token, fmt).date()
            except ValueError:
                continue
    return None


def parse_amount(text: str | None) -> Decimal | None:
    """Parse an amount string into a signed Decimal quantized to cents.

    Handles currency symbols/codes, thousands separators, European decimal
    commas, parentheses, trailing minus signs, and DR/CR suffixes.
    """
    if text is None:
        return None
    cleaned = text.strip().replace("\xa0", " ")
    if not cleaned:
        return None

    for code in _CURRENCY_CODES:
        cleaned = re.sub(rf"\b{code}\b", " ", cleaned, flags=re.IGNORECASE)
    for symbol in _CURRENCY_SYMBOLS:
        cleaned = cleaned.replace(symbol, "")
    cleaned = cleaned.strip()

    negative = False
    match = _DEBIT_SUFFIX.match(cleaned)
    if match:
        cleaned = match.group(1).strip()
        negative = match.group(2).upper() == "DR"

    if cleaned.startswith("(") and cleaned.endswith(")"):
        negative = True
        cleaned = cleaned[1:-1]
    if cleaned.endswith("-"):
        negative = True
        cleaned = cleaned[:-1]
    if cleaned.startswith("+"):
        cleaned = cleaned[1:]
    cleaned = cleaned.strip()

    try:
        value = Decimal(_normalize_number_separators(cleaned))
        if negative:
            value = -value
        return value.quantize(QUANTIZED)
    except InvalidOperation:
        return None


def normalize_merchant(text: str | None) -> str:
    """Clean a raw merchant string: uppercase, strip processor prefixes,
    trailing store numbers, long digit runs, and state codes."""
    if not text:
        return ""
    cleaned = text.upper().strip()

    for prefix in _PROCESSOR_PREFIXES:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :].lstrip("*").strip()
            break

    cleaned = _LONG_DIGIT_RUN.sub(" ", cleaned)
    cleaned = _TRAILING_STORE_NUMBER.sub("", cleaned)
    cleaned = _STATE_SUFFIX.sub("", cleaned)
    return _WHITESPACE_RUN.sub(" ", cleaned).strip()


def _normalize_number_separators(text: str) -> str:
    if "," in text:
        last_comma = text.rfind(",")
        tail = text[last_comma + 1 :]
        if "." not in text and len(tail) == 2 and tail.isdigit():
            text = text.replace(",", ".")
        else:
            text = text.replace(",", "")
    return text.replace(" ", "").replace("'", "")


def _decode(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("latin-1")


def _detect_delimiter(text: str) -> str:
    first_line = text.split("\n", 1)[0]
    counts = {delimiter: first_line.count(delimiter) for delimiter in (",", ";", "\t")}
    best = max(counts, key=lambda d: counts[d])
    return best if counts[best] > 0 else ","


def _clean_headers(header: list[str]) -> list[str]:
    return [cell.strip().lstrip("\ufeff") for cell in header]


def _cell(cells: list[str], index: int | None) -> str:
    if index is None or index >= len(cells):
        return ""
    return cells[index]


def _parse_row(
    cells: list[str], mapping: ColumnMapping, row_number: int
) -> ParsedRow | ParseError:
    date_text = _cell(cells, mapping.date)
    parsed_date = parse_date(date_text)
    if parsed_date is None:
        return ParseError(
            row_number, f"unparseable date: {date_text or '<empty>'!r}"
        )

    if mapping.debit is not None or mapping.credit is not None:
        amount: Decimal | ParseError = _split_amount(cells, mapping, row_number)
    else:
        amount_text = _cell(cells, mapping.amount)
        parsed_amount = parse_amount(amount_text) if amount_text else None
        if parsed_amount is None:
            return ParseError(
                row_number, f"unparseable amount: {amount_text or '<empty>'!r}"
            )
        amount = parsed_amount
    if isinstance(amount, ParseError):
        return amount

    description = _cell(cells, mapping.description) or None
    return ParsedRow(
        row_number=row_number,
        posted_date=parsed_date,
        description=description,
        merchant_raw=normalize_merchant(description),
        amount=amount,
    )


def _split_amount(
    cells: list[str], mapping: ColumnMapping, row_number: int
) -> Decimal | ParseError:
    debit_text = _cell(cells, mapping.debit)
    credit_text = _cell(cells, mapping.credit)

    if debit_text:
        debit = parse_amount(debit_text)
        if debit is None:
            return ParseError(row_number, f"unparseable debit amount: {debit_text!r}")
    else:
        debit = Decimal("0")

    if credit_text:
        credit = parse_amount(credit_text)
        if credit is None:
            return ParseError(row_number, f"unparseable credit amount: {credit_text!r}")
    else:
        credit = Decimal("0")

    if debit == 0 and credit == 0:
        return ParseError(row_number, "both debit and credit amounts are empty")

    return credit - debit
