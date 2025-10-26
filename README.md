# WeGather Mail Studio

WeGather Mail Studio is a web application for composing and sending personalized event emails to a CSV list of attendees.

It includes a rich-text editor, direct HTML editing, a live email preview, CSV validation, test emails, custom branding, and bulk-send progress tracking.

## Project structure

```text
.
├── email-job-backend/    # Flask API, email renderer, CSV validation, and SMTP jobs
└── emailjob-frontend/    # Browser interface built with HTML, CSS, and JavaScript
```

## Features

- Rich-text and HTML editor tabs
- Desktop and mobile email previews
- `{{first_name}}`, `{{name}}`, and `{{event}}` personalization
- CSV recipient validation
- Custom accent color, logo, button, preheader, and footer
- Test-email delivery before starting a campaign
- Background bulk-email processing with progress reporting
- SMTP credentials stored outside source control

## Requirements

- Python 3.10 or newer
- Access to an SMTP email account

## Setup

Clone the repository and open a terminal in its root directory.

### 1. Configure the backend

```powershell
cd email-job-backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Open `email-job-backend/.env` and enter your SMTP settings:

```env
SMTP_SERVER=smtp.example.com
SMTP_PORT=465
SMTP_USER=mailer@example.com
SMTP_PASSWORD=replace-me
SMTP_FROM=WeGatherEvents <mailer@example.com>
FRONTEND_ORIGIN=http://localhost:5265
PORT=5000
FLASK_DEBUG=0
```

The `.env` file is ignored by Git and should never be committed.

## Start the application

The backend and frontend run in separate terminals.

### Terminal 1 — backend

```powershell
cd email-job-backend
.\.venv\Scripts\Activate.ps1
python app.py
```

The API will be available at `http://localhost:5000/api`.

### Terminal 2 — frontend

From the repository root:

```powershell
cd emailjob-frontend
python -m http.server 5265
```

Open [http://localhost:5265](http://localhost:5265) in your browser.

## Recipient CSV format

Upload a UTF-8 CSV file containing these exact, case-sensitive column titles:

```csv
first_name,last_name,email
Jordan,Lee,jordan@example.com
Ada,Lovelace,ada@example.com
```

The backend uses `first_name` for `{{first_name}}` and combines `first_name` with `last_name` for `{{name}}`. Rows with invalid email addresses are skipped and reported by the interface.

A ready-to-copy example is available at `email-job-backend/sample-attendees.csv`.

## Personalization

The following placeholders can be used in the subject and message:

| Placeholder | Value |
| --- | --- |
| `{{first_name}}` | Recipient's first name |
| `{{name}}` | Recipient's combined first and last name |
| `{{event}}` | Event name entered in the campaign form |

Example:

```text
Hello {{first_name}},

Your registration for {{event}} is confirmed.
```

Use **Send test** to verify the rendered email before sending the campaign to the uploaded CSV list.

## Run tests

Backend tests do not send real emails:

```powershell
cd email-job-backend
.\.venv\Scripts\Activate.ps1
python -m unittest -v
```

## Deployment note

Campaign state is currently kept in memory and is intended for a single Flask process. A production deployment that requires multiple workers or durable job history should use a persistent database and a task queue such as Celery or RQ.
