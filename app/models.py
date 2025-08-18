from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    api_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    loans: Mapped[list[Loan]] = relationship(
        "Loan", back_populates="owner", cascade="all, delete-orphan"
    )


class Loan(Base):
    __tablename__ = "loans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    amount: Mapped[float] = mapped_column(Numeric(18, 2))
    annual_interest_rate: Mapped[float] = mapped_column(Float)
    term_months: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    owner: Mapped[User] = relationship("User", back_populates="loans")

    shared_with: Mapped[list[LoanShare]] = relationship(
        "LoanShare", back_populates="loan", cascade="all, delete-orphan"
    )


class LoanShare(Base):
    __tablename__ = "loan_shares"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    loan_id: Mapped[int] = mapped_column(ForeignKey("loans.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    loan: Mapped[Loan] = relationship("Loan", back_populates="shared_with")
    user: Mapped[User] = relationship("User")
