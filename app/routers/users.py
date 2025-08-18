from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import generate_api_key, get_db
from app.models import User
from app.schemas import UserCreate, UserOut

router = APIRouter()


@router.post("/", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="User with email already exists")
    api_key = generate_api_key()
    user = User(email=payload.email, name=payload.name, api_key=api_key)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/{email}/api-key")
def get_user_api_key(email: str, db: Session = Depends(get_db)):
    """Get a user's API key by email address"""
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    return {"email": user.email, "api_key": user.api_key}


@router.get("/", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)):
    """List all users (useful for testing)"""
    users = db.query(User).all()
    return users
