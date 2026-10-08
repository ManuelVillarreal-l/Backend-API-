# RutaSegura — Backend / API / Database

Smart rural school transport system. REST API built with FastAPI.

> Code, comments and stored values are in English.
> Everything the end user reads is in Spanish: the Swagger page (buttons, titles, dialogs,
> see `app/docs_es.py`) and every error message (see `app/errors.py`).

## Tech stack
- Python 3.13
- FastAPI + Swagger UI
- SQLAlchemy 2
- SQLite for local development, PostgreSQL in the cloud
- JWT authentication with role-based access control
- Data structures implemented from scratch (`app/structures`)
- Pytest automated tests

## Project structure
```
app/
  main.py          FastAPI app, routers and startup
  database.py      Engine, session and DATABASE_URL handling
  models.py        Database tables
  schemas.py       Request/response schemas
  constants.py     Roles, trip statuses, event types, etc.
  auth.py          Password hashing, JWT and roles
  docs_es.py       Swagger UI translated to Spanish
  errors.py        Spanish error messages (401, 404, 422...)
  seed.py          Demo data
  routers/         Endpoints by module
  structures/      Stack, Queue, lists, BST, AVL, N-ary tree, Graph
tests/             API and data structure tests
```

## Run locally (Windows / VS Code)
```
py -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```
Or double-click `start_server.bat` once the virtual environment exists.

- API: http://127.0.0.1:8000
- Swagger: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/health

## Run the tests
```
pytest -v
```
Or double-click `run_tests.bat`. Tests use a temporary `test_rutasegura.db`, so the real database is never modified.

## Demo users
| Role | Email | Password |
|---|---|---|
| coordinator | admin@rutasegura.com | Admin123* |
| driver | conductor@rutasegura.com | Conductor123* |
| guardian | acudiente@rutasegura.com | Acudiente123* |

In Swagger, click **Autorizar** and type the email in `username` (leave `client_id` and `client_secret` empty).

## Stored values
| Field | Values |
|---|---|
| `role` | `guardian`, `driver`, `monitor`, `coordinator` |
| `trip.status` | `scheduled`, `in_progress`, `finished` |
| `event_type` | `boarding`, `drop_off` |
| `method` | `qr`, `manual` |
| `weather` (AI) | `normal`, `cloudy`, `rain`, `storm` |
| `road_condition` (AI) | `good`, `fair`, `bad`, `closed` |

## Features
- JWT login (JSON for the frontend, form for Swagger Authorize)
- Users and roles
- Students with QR code
- Routes and stops
- Trips (create, start, finish)
- Boarding and drop-off, manual or by QR scan
- Attendance history per student
- Heuristic delay prediction
- Basic stop-order suggestion

## Data structures and their use
| Structure | Use in RutaSegura |
|---|---|
| Stack | Undo route changes |
| Queue | Students waiting to board |
| Linked list | Sequence of stops |
| Doubly linked list | Outbound / return trip |
| Circular list | Daily route cycle |
| Circular doubly list | Driver rotation |
| BST | Student search |
| AVL tree | Balanced student index |
| N-ary tree | Institution → campus → grade → student |
| Graph (Dijkstra) | Rural road network and shortest path |

## Database
Locally, `rutasegura.db` is created automatically with demo data.
In production set `DATABASE_URL` to a PostgreSQL URL; `postgres://` and `postgresql://` URLs are converted to `postgresql+psycopg://` automatically.

## Deployment
`render.yaml` defines the API service and a PostgreSQL database for Render.
`.env` is excluded by `.gitignore`; set `DATABASE_URL` and `SECRET_KEY` as environment variables in the cloud.







