from fastapi import FastAPI

from app.routers import users, loans
from app.init_db import init_db

app = FastAPI(title="Greystone Loan Amortization API")

# Ensure DB is ready even in test contexts without startup events
init_db()

app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(loans.router, prefix="/loans", tags=["loans"])


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/")
def root():
    return "Hello World"

@app.on_event("startup")
def on_startup():
    init_db()
