from datetime import date
from decimal import Decimal

import pytest

from app.ingest.parser import (
    ColumnMappingError,
    ParsedRow,
    ParseError,
    detect_column_mapping,
    normalize_merchant,
    parse_amount,
    parse_csv,
    parse_date,
)


def _rows_and_errors(data: str) -> tuple[list[ParsedRow], list[ParseError]]:
    result = parse_csv(data.encode())
    return result.rows, result.errors


class TestColumnMapping:
    def test_debit_credit_headers(self) -> None:
        mapping = detect_column_mapping(["Date", "Description", "Debit", "Credit"])
        assert mapping.date == 0
        assert mapping.description == 1
        assert mapping.debit == 2
        assert mapping.credit == 3
        assert mapping.amount is None

    def test_single_amount_header(self) -> None:
        mapping = detect_column_mapping(["Posted Date", "Memo", "Amount"])
        assert mapping.date == 0
        assert mapping.description == 1
        assert mapping.amount == 2
        assert mapping.debit is None
        assert mapping.credit is None

    def test_debit_amount_is_not_single_amount(self) -> None:
        mapping = detect_column_mapping(["Date", "Description", "Debit Amount"])
        assert mapping.amount is None
        assert mapping.debit == 2

    def test_unmappable_headers(self) -> None:
        with pytest.raises(ColumnMappingError):
            detect_column_mapping(["Foo", "Bar", "Baz"])
        with pytest.raises(ColumnMappingError):
            detect_column_mapping(["Description", "Amount"])


class TestParseAmount:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("4.50", Decimal("4.50")),
            ("$1,234.56", Decimal("1234.56")),
            ("USD 45", Decimal("45.00")),
            ("€12.99", Decimal("12.99")),
            ("(45.00)", Decimal("-45.00")),
            ("45.00-", Decimal("-45.00")),
            ("-123.45", Decimal("-123.45")),
            ("+123.45", Decimal("123.45")),
            ("123.45DR", Decimal("-123.45")),
            ("123.45CR", Decimal("123.45")),
            ("1234,56", Decimal("1234.56")),
            ("1'234.56", Decimal("1234.56")),
            ("0", Decimal("0.00")),
            ("", None),
            ("abc", None),
        ],
    )
    def test_formats(self, text: str, expected: Decimal | None) -> None:
        assert parse_amount(text) == expected


class TestParseDate:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("2025-01-05", date(2025, 1, 5)),
            ("2025/01/05", date(2025, 1, 5)),
            ("2025.01.05", date(2025, 1, 5)),
            ("20250105", date(2025, 1, 5)),
            ("01/05/2025", date(2025, 1, 5)),
            ("31/12/2024", date(2024, 12, 31)),
            ("31.12.2024", date(2024, 12, 31)),
            ("31-12-2024", date(2024, 12, 31)),
            ("Jan 5, 2025", date(2025, 1, 5)),
            ("05-Jan-2025", date(2025, 1, 5)),
            ("2025-01-05T10:30:00", date(2025, 1, 5)),
            ("01/05/2025 10:30:00", date(2025, 1, 5)),
            ("not-a-date", None),
            ("", None),
        ],
    )
    def test_formats(self, text: str, expected: date | None) -> None:
        assert parse_date(text) == expected


class TestNormalizeMerchant:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("SQ *COFFEE SHOP", "COFFEE SHOP"),
            ("SQ*BAKERY", "BAKERY"),
            ("TST*AMAZON PRIME", "AMAZON PRIME"),
            ("walmart #1234", "WALMART"),
            ("7-ELEVEN 12345", "7-ELEVEN"),
            ("SHELL OIL 5744274842", "SHELL OIL"),
            ("PAYPAL *SPOTIFY CA", "SPOTIFY"),
            ("COFFEE SHOP CA", "COFFEE SHOP"),
            ("uber   trip", "UBER TRIP"),
            ("", ""),
            (None, ""),
        ],
    )
    def test_cleaning(self, raw: str | None, expected: str) -> None:
        assert normalize_merchant(raw) == expected


class TestParseCsv:
    def test_split_columns_and_errors(self) -> None:
        data = (
            "Date,Description,Debit,Credit\n"
            "2025-01-05,COFFEE SHOP,4.50,\n"
            "2025-01-06,PAYCHECK,,1250.00\n"
            "2025-01-07,GAS STATION,45.99,\n"
            "not-a-date,BAD ROW,10.00,\n"
            ",,,\n"
        )
        rows, errors = _rows_and_errors(data)
        assert len(rows) == 3
        assert len(errors) == 1
        assert errors[0].row_number == 5
        assert rows[0].amount == Decimal("-4.50")
        assert rows[1].amount == Decimal("1250.00")
        assert rows[2].amount == Decimal("-45.99")
        assert rows[0].merchant_raw == "COFFEE SHOP"

    def test_row_without_amounts_is_error(self) -> None:
        data = "Date,Description,Debit,Credit\n2025-01-08,,,\n"
        rows, errors = _rows_and_errors(data)
        assert not rows
        assert len(errors) == 1
        assert errors[0].row_number == 2
        assert "amounts are empty" in errors[0].reason

    def test_single_amount_column(self) -> None:
        data = "Posted Date,Memo,Amount\n2025-02-01,GROCERY,-23.45\n"
        rows, errors = _rows_and_errors(data)
        assert not errors
        assert rows[0].amount == Decimal("-23.45")

    def test_semicolon_delimiter_and_bom(self) -> None:
        data = "\ufeffDate;Description;Debit;Credit\n2025-03-01;TRAM;2.50;\n"
        rows, errors = _rows_and_errors(data)
        assert not errors
        assert rows[0].merchant_raw == "TRAM"

    def test_empty_file_raises(self) -> None:
        with pytest.raises(ColumnMappingError):
            parse_csv(b"")

    def test_unmappable_file_raises(self) -> None:
        with pytest.raises(ColumnMappingError):
            parse_csv(b"foo,bar\n1,2\n")

    def test_mixed_amounts(self) -> None:
        data = (
            "Date,Description,Amount\n"
            '2025-04-01,COFFEE,($4.50)\n'
            '2025-04-02,SALARY,"USD 1,250.00"\n'
            '2025-04-03,REFUND,"USD (12.34)"\n'
        )
        rows, errors = _rows_and_errors(data)
        assert not errors
        assert rows[0].amount == Decimal("-4.50")
        assert rows[1].amount == Decimal("1250.00")
        assert rows[2].amount == Decimal("-12.34")

    def test_malformed_row_is_reported_and_skipped(self) -> None:
        data = (
            "Date,Description,Amount\n"
            "2025-05-01,OK ROW,1.00\n"
            "garbage-date,BAD ROW,2.00\n"
            "2025-05-03,ALSO OK,3.00\n"
        )
        rows, errors = _rows_and_errors(data)
        assert [row.posted_date for row in rows] == [date(2025, 5, 1), date(2025, 5, 3)]
        assert len(errors) == 1
        assert errors[0].row_number == 3
        assert "unparseable date" in errors[0].reason
