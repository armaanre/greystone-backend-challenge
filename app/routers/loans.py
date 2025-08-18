from __future__ import annotations

from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.auth import get_current_user, get_db
from app.models import Loan, LoanShare, User
from app.schemas import (
    LoanCreate,
    LoanOut,
    LoanScheduleItem,
    LoanShareRequest,
    LoanSummary,
)
from app.services import build_amortization_schedule, summarize_schedule_for_month

router = APIRouter()


def assert_can_access_loan(loan: Loan, user: User, db: Session) -> None:
    if loan.owner_id == user.id:
        return
    share = (
        db.query(LoanShare)
        .filter(LoanShare.loan_id == loan.id, LoanShare.user_id == user.id)
        .first()
    )
    if not share:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found")


@router.post("/", response_model=LoanOut, status_code=status.HTTP_201_CREATED)
def create_loan(
    payload: LoanCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    loan = Loan(
        owner_id=current_user.id,
        amount=float(payload.amount),
        annual_interest_rate=float(payload.annual_interest_rate),
        term_months=payload.term_months,
    )
    db.add(loan)
    db.commit()
    db.refresh(loan)
    return loan


@router.get("/", response_model=List[LoanOut])
def list_loans(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Loans owned by the user or shared with the user
    owned = db.query(Loan).filter(Loan.owner_id == current_user.id)
    shared_ids = [
        share.loan_id
        for share in db.query(LoanShare).filter(LoanShare.user_id == current_user.id).all()
    ]
    loans = owned.union(db.query(Loan).filter(Loan.id.in_(shared_ids))).all()
    return loans


@router.get("/{loan_id}/schedule", response_model=List[LoanScheduleItem])
def get_schedule(
    loan_id: int = Path(..., gt=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    loan = db.query(Loan).filter(Loan.id == loan_id).first()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    assert_can_access_loan(loan, current_user, db)
    schedule = build_amortization_schedule(
        amount=Decimal(str(loan.amount)),
        annual_interest_rate_percent=Decimal(str(loan.annual_interest_rate)),
        term_months=loan.term_months,
    )
    return schedule


@router.get("/{loan_id}/summary", response_model=LoanSummary)
def get_summary(
    loan_id: int = Path(..., gt=0),
    month: int = Query(..., gt=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    loan = db.query(Loan).filter(Loan.id == loan_id).first()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    assert_can_access_loan(loan, current_user, db)
    if month > loan.term_months:
        raise HTTPException(status_code=400, detail="Month exceeds loan term")
    schedule = build_amortization_schedule(
        amount=Decimal(str(loan.amount)),
        annual_interest_rate_percent=Decimal(str(loan.annual_interest_rate)),
        term_months=loan.term_months,
    )
    summary = summarize_schedule_for_month(
        schedule=schedule,
        month=month,
        amount=Decimal(str(loan.amount)),
        annual_interest_rate_percent=Decimal(str(loan.annual_interest_rate)),
    )
    return summary


@router.post("/{loan_id}/share", status_code=status.HTTP_204_NO_CONTENT)
def share_loan(
    loan_id: int,
    payload: LoanShareRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    loan = db.query(Loan).filter(Loan.id == loan_id).first()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    if loan.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the owner can share this loan")

    target_user = db.query(User).filter(User.email == payload.email).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found")
    if target_user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot share loan with yourself")

    existing = (
        db.query(LoanShare)
        .filter(LoanShare.loan_id == loan.id, LoanShare.user_id == target_user.id)
        .first()
    )
    if existing:
        return

    share = LoanShare(loan_id=loan.id, user_id=target_user.id)
    db.add(share)
    db.commit()
    return
