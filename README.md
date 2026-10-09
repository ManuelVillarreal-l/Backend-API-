# RutaSegura — Backend / API

Smart rural school transport system. REST API built with FastAPI (version 2.0).

> Code, comments and stored values are in English.
> Everything the end user reads is in Spanish: the Swagger page (`app/docs_es.py`) and every
> error message (`app/errors.py`, `app/validation.py`).

## What is new in version 2
| Requirement | How it is solved |
|---|---|
| More tables | **28 tables** (`app/models.py`): 10 catalogs, organization, people, routes, operation, security, AI |
| Roles in their own table | `roles` table related to `users.role_id`; permissions check `user.role.code` |
| Weather and road condition in the database | `weather_conditions` and `road_conditions` tables, editable with `POST/PUT /api/catalogs/...`; nothing is hardcoded |
| Password encrypted in the frontend, never stored | The browser sends `SHA-256(email:password)` (64 hex). The server stores `PBKDF2-SHA256` (310 000 iterations + salt) of that digest. A plain password is rejected (422) |
| Password never visible | No endpoint returns it; `UserOut` has no password field |
| Token expires every 30 minutes | JWT with `exp`, `iat`, `jti`; `ACCESS_TOKEN_EXPIRE_MINUTES=30`; expired token → 401 "Su sesión venció" |
| Validate forms with regular expressions | `app/validation.py`: names, e-mail, phone, document, plate, license, QR, codes, free text… with min/max lengths |
| Do not accept huge inputs | Every text has `max_length`; extra fields are forbidden; requests larger than 64 KB → 413 |
| Brute force | Account locked 15 min after 5 failed logins (`login_attempts`) → 429 |
| No public sign-up | Only the coordinator creates users (`POST /api/users/`) |

## New features
- **GPS**: the bus sends its position (`POST /api/trips/{id}/locations`); geofence of 600 m warns the guardians that the bus is arriving; ETA to any stop (`GET /api/trips/{id}/eta`).
- **QR**: scan of the student ID card (`POST /api/attendance/scan`, BST lookup); the action (boarding / drop-off) is deduced from the student state.
- **Offline mode**: events saved without signal are sent later (`POST /api/attendance/sync`), idempotent with `client_event_id`.
- **Artificial intelligence** (`app/ai.py`, pure Python):
  - Delay prediction with multiple linear regression trained with the real finished trips (R² ≈ 0.95 with the demo data).
  - Route optimization: nearest neighbor + 2-opt over GPS distances (39 % shorter on Ruta Rural 02).
  - Absence risk per student, also on rainy days.
  - Current weather from Open-Meteo mapped to the weather catalog.
- Incidents, notifications, audit log, attendance summary, monitor and driver rotation.

## Data structures and their use
| Structure | Use in RutaSegura | Endpoint |
|---|---|---|
| Graph + Dijkstra | Shortest path between stops using road segments | `GET /api/routes/{id}/shortest-path` |
| Queue | Students still to board, in stop order | `GET /api/trips/{id}/queue` |
| Stack | Undo the last boarding / drop-off | `POST /api/trips/{id}/undo` |
| Linked list | Walk the remaining stops to compute the ETA | `GET /api/trips/{id}/eta` |
| Doubly linked list | Outbound and return itinerary | `GET /api/routes/{id}/itinerary` |
| Circular list | Monitor rotation on business days | `GET /api/trips/rotation/monitors` |
| Circular doubly linked list | Driver rotation (previous / next) | `GET /api/users/drivers/rotation` |
| BST | QR code lookup when scanning | `POST /api/attendance/scan` |
| AVL tree | Student search by name or last-name prefix | `GET /api/students/search` |
| N-ary tree | Institution → campus → grade → students | `GET /api/schools/tree` |

## Project structure
```
app/
  main.py          FastAPI app, body-size limit, routers
  database.py      Engine, session and DATABASE_URL handling
  models.py        28 tables
  validation.py    Regular expressions and length limits
  schemas.py       Request / response schemas
  auth.py          Password hashing, 30-minute JWT, lockout, roles
  services.py      Permissions by role, catalogs, audit, notifications
  operations.py    Boarding rules, geofence and ETA
  ai.py            Regression, route optimization, absence risk, weather
  docs_es.py       Swagger in Spanish + password hashing in the browser
  errors.py        Spanish error messages
  seed.py          Demo data (3 weeks of history)
  routers/         auth, users, catalogs, organization, routes, students,
                   trips, attendance, monitoring, intelligence
  structures/      The 10 data structures
tests/             Security, API flow and data structure tests
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

If you had a `rutasegura.db` from version 1, delete it: the tables changed and it is recreated with demo data.

## Run the tests
```
pytest -v
```
Or double-click `run_tests.bat`. Tests use a temporary `test_rutasegura.db`; to run them against
PostgreSQL set `TEST_DATABASE_URL` to an empty database.

## Demo users
| Role | Email | Password |
|---|---|---|
| coordinator | admin@rutasegura.com | Admin123* |
| driver | conductor@rutasegura.com, conductor2@…, conductor3@… | Conductor123* |
| monitor | monitor@rutasegura.com, monitor2@… | Monitor123* |
| guardian | acudiente@rutasegura.com, acudiente2@… to acudiente4@… | Acudiente123* |

In Swagger click **Autorizar**, type the e-mail in `username` and the normal password: the page
converts it to SHA-256 before sending it (the same as the web app).

## Deployment
`render.yaml` defines the API service and the PostgreSQL database for Render
(`ACCESS_TOKEN_EXPIRE_MINUTES=30`). `.env` is excluded by `.gitignore`.
