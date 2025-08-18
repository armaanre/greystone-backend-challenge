# Greystone Backend Challenge – FastAPI Loan Amortization API

## Quickstart

1. Create a virtual environment and install dependencies:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Run the API:

   ```bash
   uvicorn app.main:app --reload
   ```

3. Open the interactive docs at `http://localhost:8000/docs`.

## Database setup

- By default, the app uses SQLite stored at `app.db` (see `app/database.py`).
- Tables are auto-created on app startup and during tests. There is no manual migration required.

## API Overview

- Create user: `POST /users/` -> returns `api_key`
- Auth header: `X-API-Key: <api_key>`
- Create loan: `POST /loans/`
- List loans: `GET /loans/`
- Loan schedule: `GET /loans/{loan_id}/schedule`
- Loan summary: `GET /loans/{loan_id}/summary?month={n}`
- Share loan: `POST /loans/{loan_id}/share` with `{ "email": "friend@example.com" }`

## Testing

```bash
pytest -q
```

## Notes

- Uses SQLite via SQLAlchemy 2.x
- Amortization logic implemented with `Decimal` and standard formula
- Loans are accessible to their owner and to users they are shared with

## Approach explained

This FastAPI backend creates users based on a name and email address and creates an api key for that specific user. Since loans for a given user are protected, and should only be visible to users with that given api key, it is required for viewing any loan details which was why it is required for viewing any loan data.

For testing purposes I added an endpoint to get a list of created users and their respective api keys. In a production environment this would not be available and some sort of authentication would be added to obtain these keys.

Given the api key you can view the loan details of any user and share them with other users.
