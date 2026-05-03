# P2P Recognition Portal

Lightweight internal recognition web app built with Flask and SQLAlchemy.

The current codebase supports:
- employee directory management
- magic-link sign-in
- immediate publication of non-monetary recognition
- sender-side points recognition requests with pending/edit/cancel/delete flows
- basic moderation for published non-monetary posts

The current codebase does not yet implement the full product vision in `docs/prd.md`. In particular, manager approval of points requests, budgets, points ledgering, redemption flows, and production email delivery are still pending.

## Quick Start

### Prerequisites

- Python 3.11+ recommended
- `pip`

### Install

```bash
cd /Users/huifu/Project/p2p_recog
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Optional test dependency:

```bash
pip install pytest
```

### Run the app

```bash
python app.py --debug
```

By default the app starts at `http://127.0.0.1:5000`.

## Configuration

### Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///instance/portal.db` | Database connection string |

### Application defaults in code

These are set in `recognition_portal/__init__.py` today:

| Setting | Default |
| --- | --- |
| `SECRET_KEY` | `dev` |
| `ALLOWED_LOGIN_DOMAINS` | `["example.com"]` |
| `MAGIC_LINK_TTL_MINUTES` | `30` |
| `PUBLIC_BASE_URL` | `http://localhost:5000` |

Notes:
- The default database is SQLite stored under `instance/portal.db`.
- Outbound email is currently a development stub: messages are printed to stdout and stored in the `notification_events` table.
- Only `DATABASE_URL` is environment-driven right now.
- If you want different login domains, public URL, or secret handling, update `create_app()` in `recognition_portal/__init__.py`.

## First-Time Bootstrap

Fresh databases have an important limitation: admin pages require an authenticated active admin, but an empty database has no employees yet.

That means you currently need to seed the first admin record outside the UI once.

### Bootstrap the first admin

Start from the repo root:

```bash
cd /Users/huifu/Project/p2p_recog
PYTHONPATH=. python - <<'PY'
from recognition_portal import create_app
from recognition_portal.db import session_scope
from recognition_portal.employee_directory import import_employees_from_csv

app = create_app()
csv_text = """name,email,role,department,region,active,manager_email
Ada Lovelace,ada@example.com,admin,Operations,US,yes,
Grace Hopper,grace@example.com,manager,Engineering,US,yes,ada@example.com
Alan Turing,alan@example.com,employee,Engineering,EU,yes,grace@example.com
Katherine Johnson,katherine@example.com,employee,Engineering,US,yes,grace@example.com
"""

with app.app_context():
    with session_scope(app) as session:
        import_employees_from_csv(session, csv_text)
PY
```

After that, you can sign in as `ada@example.com` and use the admin UI normally.

## How To Use The Software

### 1. Sign in

1. Open `http://127.0.0.1:5000/login`
2. Enter a company email such as `ada@example.com`
3. Submit the form
4. Copy the magic-link URL printed in the terminal
5. Open that URL in the browser

If the email exists in the employee directory and is active, you will get full access based on role.

### 2. Manage the employee directory

Once signed in as an admin:

1. Open `Employee directory`
2. Create employees manually, or use `Import CSV`
3. Supported CSV columns:
   - `name`
   - `email`
   - `role`
   - `department`
   - `region`
   - `active`
   - `manager_email`

Import behavior:
- email is required
- imports are atomic
- manager references are resolved by `manager_email`
- self-management is rejected

### 3. Send non-monetary recognition

From the portal home page:

1. Choose a recipient
2. Choose a category
3. Optionally add a company-value tag
4. Enter a plain-text message between 20 and 500 characters
5. Click `Publish recognition`

Current behavior:
- posts publish immediately
- posts appear in the company feed right away
- recipient and recipient manager get notification events
- self-recognition is blocked
- duplicate recognition to the same coworker is blocked for 14 days

### 4. Submit a points recognition request

From the portal home page:

1. Choose one or more recipients
2. Choose a category
3. Optionally add a company-value tag
4. Choose points per recipient: `10`, `25`, or `50`
5. Enter a plain-text message between 20 and 500 characters
6. Click `Submit points request`

Current behavior:
- requests stay in `pending_approval`
- they do not appear in the public company feed
- the sender can edit, cancel, or delete pending requests
- self-recognition is blocked
- duplicate recognition cooldown also applies here

Current limitation:
- manager approval workflow is not implemented yet

### 5. Moderate a published non-monetary recognition

Admins and relevant managers can:
- hide a recognition from the feed
- remove a recognition

This only applies to published non-monetary posts today.

## Project Structure

```text
p2p_recog/
├── app.py
├── recognition_portal/
│   ├── __init__.py
│   ├── auth.py
│   ├── db.py
│   ├── employee_directory.py
│   ├── models.py
│   ├── notifications.py
│   ├── recognitions.py
│   └── web.py
├── templates/
├── tests/
└── docs/
```

Key modules:
- `recognition_portal/auth.py`: magic-link generation, consumption, and session user loading
- `recognition_portal/employee_directory.py`: employee import and directory operations
- `recognition_portal/recognitions.py`: recognition and points-request business rules
- `recognition_portal/web.py`: Flask routes and form handling
- `recognition_portal/notifications.py`: development email stub and notification event storage

## Commands

Run the app:

```bash
python app.py --debug
```

Run the test suite:

```bash
PYTHONPATH=. pytest -q
```

Run a narrower test slice:

```bash
PYTHONPATH=. pytest -q tests/test_issue_6_points_recognition.py
```

## Current Feature Status

Implemented:
- directory import and employee admin UI
- magic-link sign-in
- access gating by employee status
- non-monetary recognition publishing
- points recognition request draft/pending flows
- basic moderation
- regression coverage for issues `#6` through `#13`

Not implemented yet:
- manager approval actions for points requests
- budget enforcement
- approved/rejected points lifecycle
- ledger and balances
- redemption workflows
- production email integration
- initial admin bootstrap through the browser

## Known Limitations

- Email delivery is simulated by printing messages to stdout.
- The first admin must be seeded outside the UI.
- SQLite is fine for local development but not a production deployment plan.
- The repo currently has no dedicated migrations system; tables are created from SQLAlchemy metadata on startup.
