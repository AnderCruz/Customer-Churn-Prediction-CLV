"""Streaming analytical access to UCI Online Retail II invoice lines."""

import hashlib
import re
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from .acquisition import SourceError, safe_members

_COLUMNS = (
    "Invoice",
    "StockCode",
    "Description",
    "Quantity",
    "InvoiceDate",
    "Price",
    "Customer ID",
    "Country",
)
_SHEETS = ("Year 2009-2010", "Year 2010-2011")
_INVOICE = re.compile(r"(?:[CA])?[0-9]{6}", re.IGNORECASE)
_CUSTOMER = re.compile(r"[0-9]{5}")
_PRODUCT = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._/-]{0,63}")
_MIB = 1024 * 1024


@dataclass(frozen=True, slots=True)
class RetailLine:
    """One native transaction line. Dates are UK-source wall times, prices are GBP."""

    sheet: str
    source_row: int
    invoice_id: str
    product_id: str
    description: str | None
    quantity: int
    invoice_date: datetime
    unit_price: Decimal
    customer_id: str | None
    country: str
    source_notes: tuple[str, ...] = ()

    @property
    def cancellation(self) -> bool:
        return self.invoice_id.upper().startswith("C")

    @property
    def transaction_value(self) -> Decimal:
        return self.quantity * self.unit_price


def _workbook(path: Path):
    try:
        if path.suffix.lower() != ".xlsx" or path.stat().st_size > 60 * _MIB:
            raise SourceError("Unexpected retail workbook format or size.")
        with ZipFile(path) as archive:
            for member in safe_members(archive, expanded_limit=340 * _MIB, member_limit=24):
                parts = member.filename.split("/")
                if parts[0] not in {"xl", "docProps", "_rels", "[Content_Types].xml"}:
                    raise SourceError("Unexpected retail workbook package member.")
                if not member.filename.endswith((".xml", ".rels")):
                    raise SourceError("Unexpected non-XML workbook member.")
                if "/worksheets/" not in member.filename and member.file_size > 2 * _MIB:
                    raise SourceError("Workbook metadata exceeds its size budget.")
                # The official OOXML package contains no DTDs or entity declarations.
                with archive.open(member) as stream:
                    previous = b""
                    prefix = stream.read(4)
                    if (
                        not prefix
                        or b"\x00" in prefix
                        or prefix.startswith((b"\xff\xfe", b"\xfe\xff"))
                    ):
                        raise SourceError("Unsupported workbook XML encoding.")
                    chunk = prefix
                    while chunk:
                        data = previous + chunk
                        if b"<!DOCTYPE" in data or b"<!ENTITY" in data:
                            raise SourceError("Unsafe workbook XML declaration.")
                        previous = data[-12:]
                        chunk = stream.read(_MIB)
        workbook = load_workbook(path, read_only=True, data_only=False, keep_links=False)
    except (BadZipFile, OSError, InvalidFileException, KeyError, ValueError, SyntaxError) as exc:
        if isinstance(exc, SourceError):
            raise
        raise SourceError("Malformed retail workbook.") from None
    if tuple(workbook.sheetnames) != _SHEETS:
        workbook.close()
        raise SourceError("Unexpected retail workbook sheets.")
    return workbook


def sheet_names(path: Path) -> list[str]:
    """Read the workbook inventory after validating the package."""
    workbook = _workbook(path)
    try:
        return workbook.sheetnames
    finally:
        workbook.close()


def _identifier(value) -> str:
    if isinstance(value, str) and value and value == value.strip():
        return value
    if type(value) is int:
        return str(value)
    raise ValueError


def _normalise(sheet: str, index: int, values: tuple) -> RetailLine:
    invoice, product, description, quantity, date, price, customer, country = values
    notes = []
    if isinstance(product, str) and product != product.strip():
        notes.append("trimmed_product_identifiers")
        product = product.strip()
    if type(description) is int:
        notes.append("numeric_descriptions")
        description = str(description)
    try:
        invoice = _identifier(invoice)
        product = _identifier(product)
        customer = None if customer is None else _identifier(customer)
        if (
            not _INVOICE.fullmatch(invoice)
            or not _PRODUCT.fullmatch(product)
            or (customer is not None and not _CUSTOMER.fullmatch(customer))
            or type(quantity) is not int
            or abs(quantity) > 10**7
            or not isinstance(date, datetime)
            or date.tzinfo is not None
            or not datetime(2009, 12, 1) <= date < datetime(2011, 12, 10)
            or (description is not None and not isinstance(description, str))
            or not isinstance(country, str)
            or not country.strip()
            or type(price) not in (int, float)
        ):
            raise ValueError
        price = Decimal(str(price))
        if not price.is_finite() or abs(price) > 10**7 or price.as_tuple().exponent < -6:
            raise ValueError
    except (ValueError, InvalidOperation):
        raise SourceError(f"{sheet}: invalid source field at row {index}.") from None
    return RetailLine(
        sheet,
        index,
        invoice,
        product,
        description,
        quantity,
        date,
        price,
        customer,
        country,
        tuple(notes),
    )


def iter_retail_lines(path: Path) -> Iterator[RetailLine]:
    """Stream validated lines in sheet and row order without dropping source records."""
    workbook = _workbook(path)
    try:
        for worksheet in workbook.worksheets:
            if worksheet.max_column != len(_COLUMNS) or (
                worksheet.max_row is None or not 2 <= worksheet.max_row <= 600_001
            ):
                raise SourceError("Unexpected retail worksheet dimensions.")
            rows = worksheet.iter_rows(max_col=len(_COLUMNS))
            if tuple(cell.value for cell in next(rows, ())) != _COLUMNS:
                raise SourceError("Unexpected retail worksheet header.")
            for index, cells in enumerate(rows, 2):
                if index > 600_001 or any(cell.data_type in {"f", "e"} for cell in cells):
                    raise SourceError(f"{worksheet.title}: unsupported cell or row at {index}.")
                yield _normalise(worksheet.title, index, tuple(cell.value for cell in cells))
    except (BadZipFile, SyntaxError, OSError, ValueError) as exc:
        if isinstance(exc, SourceError):
            raise
        raise SourceError("Malformed retail worksheet.") from None
    finally:
        workbook.close()


def audit_retail(path: Path) -> dict:
    """Summarise the entire source and retain signed anomalies in reported counts."""
    customers = set()
    invoices = set()
    cancellation_invoices = set()
    seen = set()
    counts: Counter = Counter()
    sheets: Counter = Counter()
    first = last = None
    for row in iter_retail_lines(path):
        sheets[row.sheet] += 1
        invoices.add(row.invoice_id)
        if row.customer_id is not None:
            customers.add(row.customer_id)
        if row.cancellation:
            cancellation_invoices.add(row.invoice_id)
        signature = hashlib.blake2b(
            repr(
                (
                    row.invoice_id,
                    row.product_id,
                    row.description,
                    row.quantity,
                    row.invoice_date,
                    row.unit_price,
                    row.customer_id,
                    row.country,
                )
            ).encode(),
            digest_size=16,
        ).digest()
        counts["duplicate_lines"] += signature in seen
        seen.add(signature)
        counts["missing_customers"] += row.customer_id is None
        counts["missing_descriptions"] += row.description is None
        counts["negative_quantities"] += row.quantity < 0
        counts["zero_quantities"] += row.quantity == 0
        counts["cancellation_lines"] += row.cancellation
        counts["cancellations_with_nonnegative_quantity"] += row.cancellation and row.quantity >= 0
        counts["non_cancellation_negative_quantities"] += not row.cancellation and row.quantity < 0
        counts["negative_unit_prices"] += row.unit_price < 0
        counts["zero_unit_prices"] += row.unit_price == 0
        counts.update(row.source_notes)
        first = row.invoice_date if first is None else min(first, row.invoice_date)
        last = row.invoice_date if last is None else max(last, row.invoice_date)
    return {
        "rows": sum(sheets.values()),
        "sheets": dict(sheets),
        "customers": len(customers),
        "invoices": len(invoices),
        "cancellation_invoices": len(cancellation_invoices),
        "first_invoice": first,
        "last_invoice": last,
        **counts,
    }
