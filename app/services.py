from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP, getcontext
from typing import List

from app.schemas import LoanScheduleItem, LoanSummary


# Set high precision for intermediate calculations
getcontext().prec = 28


TWOPLACES = Decimal("0.01")


def to_money(value: Decimal) -> Decimal:
    return value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


@dataclass
class AmortizationInput:
    amount: Decimal
    annual_interest_rate_percent: Decimal
    term_months: int


def compute_monthly_payment(amount: Decimal, annual_interest_rate_percent: Decimal, term_months: int) -> Decimal:
    principal = Decimal(amount)
    monthly_rate = Decimal(annual_interest_rate_percent) / Decimal(100) / Decimal(12)
    n = Decimal(term_months)

    if monthly_rate == 0:
        return to_money(principal / n)

    numerator = principal * monthly_rate * (1 + monthly_rate) ** n
    denominator = (1 + monthly_rate) ** n - 1
    payment = numerator / denominator
    return to_money(payment)


def build_amortization_schedule(
    amount: Decimal, annual_interest_rate_percent: Decimal, term_months: int
) -> List[LoanScheduleItem]:
    principal = Decimal(amount)
    monthly_rate = Decimal(annual_interest_rate_percent) / Decimal(100) / Decimal(12)
    monthly_payment = compute_monthly_payment(principal, annual_interest_rate_percent, term_months)

    schedule: List[LoanScheduleItem] = []
    remaining = principal

    for month in range(1, term_months + 1):
        if monthly_rate == 0:
            interest = Decimal(0)
        else:
            interest = remaining * monthly_rate
        principal_component = monthly_payment - interest
        # Guard for final rounding-induced negative balances
        if principal_component > remaining:
            principal_component = remaining
        remaining = remaining - principal_component
        schedule.append(
            LoanScheduleItem(
                month=month,
                remaining_balance=to_money(max(remaining, Decimal(0))),
                monthly_payment=to_money(monthly_payment),
            )
        )

    return schedule


def summarize_schedule_for_month(
    schedule: List[LoanScheduleItem], month: int, amount: Decimal, annual_interest_rate_percent: Decimal
) -> LoanSummary:
    monthly_rate = Decimal(annual_interest_rate_percent) / Decimal(100) / Decimal(12)
    monthly_payment = compute_monthly_payment(Decimal(amount), annual_interest_rate_percent, len(schedule))

    total_principal_paid = Decimal(0)
    total_interest_paid = Decimal(0)
    remaining = Decimal(amount)

    for item in schedule[:month]:
        if monthly_rate == 0:
            interest = Decimal(0)
        else:
            interest = remaining * monthly_rate
        principal_component = monthly_payment - interest
        if principal_component > remaining:
            principal_component = remaining
        remaining -= principal_component
        total_principal_paid += principal_component
        total_interest_paid += interest

    return LoanSummary(
        month=month,
        principal_balance=to_money(max(remaining, Decimal(0))),
        total_principal_paid=to_money(total_principal_paid),
        total_interest_paid=to_money(total_interest_paid),
    )
