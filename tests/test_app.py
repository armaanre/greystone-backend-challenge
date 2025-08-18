from decimal import Decimal

import httpx
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base
from app.models import User, Loan, LoanShare

client = TestClient(app)

@pytest.fixture(scope="session", autouse=True)
def cleanup_database():
    """Clean up database before running tests"""
    from app.database import engine
    # Drop all tables
    Base.metadata.drop_all(bind=engine)
    # Recreate all tables
    Base.metadata.create_all(bind=engine)
    yield
    # Clean up after tests
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="module")
def user():
    resp = client.post("/users/", json={"email": "alice@example.com", "name": "Alice"})
    if resp.status_code != status.HTTP_201_CREATED:
        print(f"Error response: {resp.status_code}")
        print(f"Error body: {resp.text}")
    assert resp.status_code == status.HTTP_201_CREATED
    return resp.json()


@pytest.fixture(scope="module")
def second_user():
    resp = client.post("/users/", json={"email": "bob@example.com", "name": "Bob"})
    assert resp.status_code == status.HTTP_201_CREATED
    return resp.json()


def auth_headers(api_key: str) -> dict[str, str]:
    return {"X-API-Key": api_key}


def test_create_and_list_loans(user):
    # Create loan
    payload = {"amount": "100000.00", "annual_interest_rate": "6.0", "term_months": 12}
    resp = client.post("/loans/", headers=auth_headers(user["api_key"]), json=payload)
    assert resp.status_code == status.HTTP_201_CREATED
    loan = resp.json()

    # List loans for owner
    resp = client.get("/loans/", headers=auth_headers(user["api_key"]))
    assert resp.status_code == status.HTTP_200_OK
    loans = resp.json()
    assert any(l["id"] == loan["id"] for l in loans)


def test_schedule_and_summary(user):
    # Create another short loan for deterministic schedule
    payload = {"amount": "1200.00", "annual_interest_rate": "12.0", "term_months": 12}
    resp = client.post("/loans/", headers=auth_headers(user["api_key"]), json=payload)
    loan = resp.json()

    # Schedule length
    resp = client.get(f"/loans/{loan['id']}/schedule", headers=auth_headers(user["api_key"]))
    assert resp.status_code == 200
    schedule = resp.json()
    assert len(schedule) == 12

    # Summary at month 6
    resp = client.get(
        f"/loans/{loan['id']}/summary",
        headers=auth_headers(user["api_key"]),
        params={"month": 6},
    )
    assert resp.status_code == 200
    summary = resp.json()
    assert summary["month"] == 6


def test_sharing(user, second_user):
    # Owner creates loan
    payload = {"amount": "5000.00", "annual_interest_rate": "0.0", "term_months": 5}
    resp = client.post("/loans/", headers=auth_headers(user["api_key"]), json=payload)
    loan = resp.json()

    # Share with second user
    resp = client.post(
        f"/loans/{loan['id']}/share",
        headers=auth_headers(user["api_key"]),
        json={"email": second_user["email"]},
    )
    assert resp.status_code == status.HTTP_204_NO_CONTENT

    # Second user can see the loan in list
    resp = client.get("/loans/", headers=auth_headers(second_user["api_key"]))
    assert resp.status_code == 200
    loans = resp.json()
    assert any(l["id"] == loan["id"] for l in loans)

    # And can fetch schedule
    resp = client.get(
        f"/loans/{loan['id']}/schedule",
        headers=auth_headers(second_user["api_key"]),
    )
    assert resp.status_code == 200


def test_loan_validation_errors(user):
    """Test loan creation validation errors"""
    
    # Test negative amount
    payload = {"amount": "-1000.00", "annual_interest_rate": "5.0", "term_months": 12}
    resp = client.post("/loans/", headers=auth_headers(user["api_key"]), json=payload)
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    # Test zero amount
    payload = {"amount": "0.00", "annual_interest_rate": "5.0", "term_months": 12}
    resp = client.post("/loans/", headers=auth_headers(user["api_key"]), json=payload)
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    # Test negative interest rate
    payload = {"amount": "1000.00", "annual_interest_rate": "-5.0", "term_months": 12}
    resp = client.post("/loans/", headers=auth_headers(user["api_key"]), json=payload)
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    # Test zero term months
    payload = {"amount": "1000.00", "annual_interest_rate": "5.0", "term_months": 0}
    resp = client.post("/loans/", headers=auth_headers(user["api_key"]), json=payload)
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_zero_interest_loan(user):
    """Test loan with zero interest rate"""
    payload = {"amount": "1000.00", "annual_interest_rate": "0.0", "term_months": 10}
    resp = client.post("/loans/", headers=auth_headers(user["api_key"]), json=payload)
    assert resp.status_code == status.HTTP_201_CREATED
    loan = resp.json()
    
    # Get schedule
    resp = client.get(f"/loans/{loan['id']}/schedule", headers=auth_headers(user["api_key"]))
    assert resp.status_code == 200
    schedule = resp.json()
    
    # With zero interest, monthly payment should be amount / term_months
    expected_monthly_payment = "100.00"  # String format
    assert len(schedule) == 10
    
    # All payments should be equal
    for item in schedule:
        assert item["monthly_payment"] == expected_monthly_payment
    
    # Final balance should be 0
    assert schedule[-1]["remaining_balance"] == "0.00"


def test_high_interest_loan(user):
    """Test loan with high interest rate"""
    payload = {"amount": "1000.00", "annual_interest_rate": "25.0", "term_months": 12}
    resp = client.post("/loans/", headers=auth_headers(user["api_key"]), json=payload)
    assert resp.status_code == status.HTTP_201_CREATED
    loan = resp.json()
    
    # Get schedule
    resp = client.get(f"/loans/{loan['id']}/schedule", headers=auth_headers(user["api_key"]))
    assert resp.status_code == 200
    schedule = resp.json()
    
    assert len(schedule) == 12
    
    # With high interest, early payments should be mostly interest
    first_month = schedule[0]
    last_month = schedule[-1]
    
    # Early payments should have higher remaining balance
    assert first_month["remaining_balance"] > last_month["remaining_balance"]


def test_loan_summary_calculations(user):
    """Test loan summary calculations at different months"""
    payload = {"amount": "10000.00", "annual_interest_rate": "10.0", "term_months": 24}
    resp = client.post("/loans/", headers=auth_headers(user["api_key"]), json=payload)
    assert resp.status_code == status.HTTP_201_CREATED
    loan = resp.json()
    
    # Test summary at month 1
    resp = client.get(
        f"/loans/{loan['id']}/summary",
        headers=auth_headers(user["api_key"]),
        params={"month": 1},
    )
    assert resp.status_code == 200
    summary1 = resp.json()
    
    assert summary1["month"] == 1
    assert float(summary1["principal_balance"]) > 0
    assert float(summary1["total_principal_paid"]) > 0
    assert float(summary1["total_interest_paid"]) > 0
    
    # Test summary at month 12 (halfway)
    resp = client.get(
        f"/loans/{loan['id']}/summary",
        headers=auth_headers(user["api_key"]),
        params={"month": 12},
    )
    assert resp.status_code == 200
    summary12 = resp.json()
    
    assert summary12["month"] == 12
    assert float(summary12["principal_balance"]) < float(summary1["principal_balance"])
    assert float(summary12["total_principal_paid"]) > float(summary1["total_principal_paid"])
    assert float(summary12["total_interest_paid"]) > float(summary1["total_interest_paid"])
    
    # Test summary at final month
    resp = client.get(
        f"/loans/{loan['id']}/summary",
        headers=auth_headers(user["api_key"]),
        params={"month": 24},
    )
    assert resp.status_code == 200
    summary24 = resp.json()
    
    assert summary24["month"] == 24
    assert summary24["principal_balance"] == "0.00"  # Should be fully paid off


def test_loan_summary_validation_errors(user):
    """Test loan summary validation errors"""
    payload = {"amount": "1000.00", "annual_interest_rate": "5.0", "term_months": 12}
    resp = client.post("/loans/", headers=auth_headers(user["api_key"]), json=payload)
    assert resp.status_code == status.HTTP_201_CREATED
    loan = resp.json()
    
    # Test month 0 (invalid)
    resp = client.get(
        f"/loans/{loan['id']}/summary",
        headers=auth_headers(user["api_key"]),
        params={"month": 0},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    # Test month 13 (exceeds loan term)
    resp = client.get(
        f"/loans/{loan['id']}/summary",
        headers=auth_headers(user["api_key"]),
        params={"month": 13},
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    
    # Test negative month
    resp = client.get(
        f"/loans/{loan['id']}/summary",
        headers=auth_headers(user["api_key"]),
        params={"month": -1},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_loan_schedule_accuracy(user):
    """Test that loan schedule calculations are mathematically accurate"""
    payload = {"amount": "1000.00", "annual_interest_rate": "12.0", "term_months": 12}
    resp = client.post("/loans/", headers=auth_headers(user["api_key"]), json=payload)
    assert resp.status_code == status.HTTP_201_CREATED
    loan = resp.json()
    
    # Get schedule
    resp = client.get(f"/loans/{loan['id']}/schedule", headers=auth_headers(user["api_key"]))
    assert resp.status_code == 200
    schedule = resp.json()
    
    assert len(schedule) == 12
    
    # Test that monthly payments are consistent
    monthly_payment = schedule[0]["monthly_payment"]
    for item in schedule:
        assert item["monthly_payment"] == monthly_payment
    
    # Test that remaining balance decreases over time
    for i in range(1, len(schedule)):
        assert float(schedule[i]["remaining_balance"]) <= float(schedule[i-1]["remaining_balance"])
    
    # Test that final balance is 0
    assert schedule[-1]["remaining_balance"] == "0.00"


def test_large_loan_amount(user):
    """Test loan with large amount to ensure precision handling"""
    payload = {"amount": "999999999.99", "annual_interest_rate": "5.5", "term_months": 360}
    resp = client.post("/loans/", headers=auth_headers(user["api_key"]), json=payload)
    assert resp.status_code == status.HTTP_201_CREATED
    loan = resp.json()
    
    # Get schedule
    resp = client.get(f"/loans/{loan['id']}/schedule", headers=auth_headers(user["api_key"]))
    assert resp.status_code == 200
    schedule = resp.json()
    
    assert len(schedule) == 360
    
    # Test that all amounts are properly formatted (2 decimal places)
    for item in schedule:
        # Check that amounts are strings with 2 decimal places
        assert isinstance(item["monthly_payment"], str)
        assert isinstance(item["remaining_balance"], str)
        
        # Verify decimal places
        monthly_payment_parts = item["monthly_payment"].split(".")
        remaining_balance_parts = item["remaining_balance"].split(".")
        
        assert len(monthly_payment_parts) == 2
        assert len(remaining_balance_parts) == 2
        assert len(monthly_payment_parts[1]) == 2
        assert len(remaining_balance_parts[1]) == 2


def test_loan_access_control(user, second_user):
    """Test that users can only access loans they own or are shared with"""
    # User creates a loan
    payload = {"amount": "5000.00", "annual_interest_rate": "8.0", "term_months": 12}
    resp = client.post("/loans/", headers=auth_headers(user["api_key"]), json=payload)
    assert resp.status_code == status.HTTP_201_CREATED
    loan = resp.json()
    
    # Second user should not be able to access the loan
    resp = client.get(f"/loans/{loan['id']}/schedule", headers=auth_headers(second_user["api_key"]))
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    
    resp = client.get(
        f"/loans/{loan['id']}/summary",
        headers=auth_headers(second_user["api_key"]),
        params={"month": 1},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    
    # Share the loan
    resp = client.post(
        f"/loans/{loan['id']}/share",
        headers=auth_headers(user["api_key"]),
        json={"email": second_user["email"]},
    )
    assert resp.status_code == status.HTTP_204_NO_CONTENT
    
    # Now second user should be able to access it
    resp = client.get(f"/loans/{loan['id']}/schedule", headers=auth_headers(second_user["api_key"]))
    assert resp.status_code == 200
    
    resp = client.get(
        f"/loans/{loan['id']}/summary",
        headers=auth_headers(second_user["api_key"]),
        params={"month": 1},
    )
    assert resp.status_code == 200


def test_loan_sharing_validation(user):
    """Test loan sharing validation rules"""
    payload = {"amount": "1000.00", "annual_interest_rate": "5.0", "term_months": 12}
    resp = client.post("/loans/", headers=auth_headers(user["api_key"]), json=payload)
    assert resp.status_code == status.HTTP_201_CREATED
    loan = resp.json()
    
    # Try to share with non-existent user
    resp = client.post(
        f"/loans/{loan['id']}/share",
        headers=auth_headers(user["api_key"]),
        json={"email": "nonexistent@example.com"},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    
    # Try to share with yourself
    resp = client.post(
        f"/loans/{loan['id']}/share",
        headers=auth_headers(user["api_key"]),
        json={"email": user["email"]},
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    
    # Try to share someone else's loan
    second_user = client.post("/users/", json={"email": "charlie@example.com", "name": "Charlie"}).json()
    resp = client.post(
        f"/loans/{loan['id']}/share",
        headers=auth_headers(second_user["api_key"]),
        json={"email": "dave@example.com"},
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN
