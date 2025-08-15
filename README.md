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

Common tasks:

- Initialize (or re-initialize) the local SQLite DB:
  ```bash
  rm -f app.db
  python3 -c "from app.init_db import init_db; init_db(); print('DB ready')"
  ```

- Change the DB location/engine: edit `SQLALCHEMY_DATABASE_URL` in `app/database.py`, for example:
  - Postgres: `postgresql+psycopg://user:pass@localhost:5432/greystone`
  - File-based SQLite at a specific path: `sqlite:////absolute/path/to/app.db`

After changing the URL, run the init snippet above once to create tables.

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