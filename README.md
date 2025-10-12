# WeGather Mail Studio

A separated frontend and Flask backend for composing personalized HTML event emails and sending them to attendees from a CSV file.

## Project layout

- `emailjob-frontend/` — responsive HTML, CSS, and JavaScript interface with rich-text and HTML editor tabs, live preview, CSV validation, test delivery, and campaign progress.
- `email-job-backend/` — Flask API for template rendering, CSV validation, SMTP delivery, and background email jobs.

The original one-off Python scripts remain in the repository for reference and have not been modified by this rebuild.

## CSV format

Use these exact, case-sensitive column titles:

```csv
first_name,last_name,email
Jordan,Lee,jordan@example.com
```

`first_name` and `last_name` are combined to replace `{{name}}`. The event name entered in the composer replaces `{{event}}`.

## Run locally

Open two PowerShell terminals from this repository.

Backend:

```powershell
cd email-job-backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env with real SMTP credentials
python app.py
```

Frontend:

```powershell
cd emailjob-frontend
python -m http.server 5173
```

Then open `http://localhost:5173`. By default, the frontend calls `http://localhost:5000/api`.

SMTP configuration lives in `email-job-backend/.env`. This file is ignored by Git so credentials are not committed.

## Test

No real email is sent by the automated tests:

```powershell
cd email-job-backend
python -m unittest -v
```

## Production notes

The in-memory background job store is suitable for a single-process deployment. For multiple workers or durable job history, replace it with Celery/RQ plus Redis and store campaign results in a database. Restrict `FRONTEND_ORIGIN`, run behind HTTPS, and keep SMTP credentials outside version control.
