from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, EmailStr, Field, PositiveInt, condecimal


Money = condecimal(max_digits=18, decimal_places=2)
Rate = condecimal(max_digits=7, decimal_places=4)  # percentage, e.g. 6.5 means 6.5%


class UserCreate(BaseModel):
    email: EmailStr
    name: Optional[str] = None


class UserOut(BaseModel):
    id: int
    email: EmailStr
    name: Optional[str] = None
    api_key: str

    class Config:
        from_attributes = True


class LoanCreate(BaseModel):
    amount: Money = Field(..., gt=0)
    annual_interest_rate: Rate = Field(..., ge=0)
    term_months: PositiveInt


class LoanOut(BaseModel):
    id: int
    owner_id: int
    amount: Money
    annual_interest_rate: Rate
    term_months: PositiveInt

    class Config:
        from_attributes = True


class LoanScheduleItem(BaseModel):
    month: PositiveInt
    remaining_balance: Money
    monthly_payment: Money


class LoanSummary(BaseModel):
    month: PositiveInt
    principal_balance: Money
    total_principal_paid: Money
    total_interest_paid: Money


class LoanShareRequest(BaseModel):
    email: EmailStr
