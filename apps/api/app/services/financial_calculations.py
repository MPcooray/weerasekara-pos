from dataclasses import dataclass


@dataclass(frozen=True)
class CalculationLine:
    quantity: int
    unit_price_minor: int
    line_discount_minor: int = 0
    tax_rate_bps: int = 0
    tax_exempt: bool = False
    tax_inclusive: bool = True


@dataclass(frozen=True)
class CalculatedLine:
    subtotal_minor: int
    line_discount_minor: int
    invoice_discount_minor: int
    taxable_minor: int
    tax_minor: int
    total_minor: int


@dataclass(frozen=True)
class FinancialTotals:
    lines: tuple[CalculatedLine, ...]
    subtotal_minor: int
    line_discount_minor: int
    invoice_discount_minor: int
    discount_minor: int
    taxable_minor: int
    tax_minor: int
    total_minor: int
    paid_minor: int
    outstanding_minor: int


def round_ratio_half_up(numerator: int, denominator: int) -> int:
    if numerator < 0 or denominator <= 0:
        raise ValueError("Rounding inputs must be non-negative with a positive denominator")
    quotient, remainder = divmod(numerator, denominator)
    return quotient + (1 if remainder * 2 >= denominator else 0)


def _allocate(amount: int, weights: list[int]) -> list[int]:
    total = sum(weights)
    if amount == 0:
        return [0] * len(weights)
    if total <= 0 or amount > total:
        raise ValueError("Invoice discount cannot exceed the discounted subtotal")
    allocations = [(amount * weight) // total for weight in weights]
    remaining = amount - sum(allocations)
    order = sorted(range(len(weights)), key=lambda i: (-(amount * weights[i] % total), i))
    for index in order[:remaining]:
        allocations[index] += 1
    return allocations


def calculate_totals(
    lines: list[CalculationLine], *, invoice_discount_minor: int = 0, paid_minor: int = 0
) -> FinancialTotals:
    if not lines:
        raise ValueError("At least one line is required")
    if invoice_discount_minor < 0 or paid_minor < 0:
        raise ValueError("Discount and payment amounts cannot be negative")
    subtotals: list[int] = []
    net_lines: list[int] = []
    for line in lines:
        if line.quantity <= 0 or line.unit_price_minor < 0:
            raise ValueError("Quantity must be positive and unit price cannot be negative")
        if not 0 <= line.tax_rate_bps <= 100_000:
            raise ValueError("Tax rate is outside the supported range")
        subtotal = line.quantity * line.unit_price_minor
        if not 0 <= line.line_discount_minor <= subtotal:
            raise ValueError("Line discount cannot exceed its line subtotal")
        subtotals.append(subtotal)
        net_lines.append(subtotal - line.line_discount_minor)
    allocations = _allocate(invoice_discount_minor, net_lines)
    calculated: list[CalculatedLine] = []
    for line, subtotal, net, allocation in zip(
        lines, subtotals, net_lines, allocations, strict=True
    ):
        discounted = net - allocation
        rate = 0 if line.tax_exempt else line.tax_rate_bps
        if line.tax_inclusive:
            tax = round_ratio_half_up(discounted * rate, 10_000 + rate) if rate else 0
            taxable = discounted - tax
            total = discounted
        else:
            taxable = discounted
            tax = round_ratio_half_up(taxable * rate, 10_000) if rate else 0
            total = taxable + tax
        calculated.append(
            CalculatedLine(subtotal, line.line_discount_minor, allocation, taxable, tax, total)
        )
    total = sum(item.total_minor for item in calculated)
    if paid_minor > total:
        raise ValueError("Payment cannot exceed the invoice total")
    return FinancialTotals(
        tuple(calculated),
        sum(subtotals),
        sum(x.line_discount_minor for x in lines),
        invoice_discount_minor,
        sum(x.line_discount_minor for x in lines) + invoice_discount_minor,
        sum(x.taxable_minor for x in calculated),
        sum(x.tax_minor for x in calculated),
        total,
        paid_minor,
        total - paid_minor,
    )


def calculate_balance(total_minor: int, paid_minor: int) -> int:
    """Return an invoice balance using the same integer-money invariants as checkout."""
    if total_minor < 0 or paid_minor < 0:
        raise ValueError("Invoice total and paid amount cannot be negative")
    if paid_minor > total_minor:
        raise ValueError("Payment cannot exceed the outstanding balance")
    return total_minor - paid_minor
