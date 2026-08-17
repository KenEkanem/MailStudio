# Starting WeGather Mail Studio

Two processes, run in separate terminals from the repo root: the Flask API
(`email-job-backend`) and a static file server for the browser UI
(`emailjob-frontend`).

## 1. Backend setup (one-time)

```bash
cd email-job-backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `email-job-backend/.env` with real SMTP credentials before sending any
mail. The app runs fine without valid SMTP creds for browsing the UI, editing
templates, and validating CSVs — sending will just fail until they're set.

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

## 2. Run the backend

```bash
cd email-job-backend
source .venv/bin/activate
python app.py
```

API listens on `http://localhost:5000/api`.

## 3. Run the frontend

From the repo root, in a second terminal:

```bash
cd emailjob-frontend
python3 -m http.server 5265
```

Open `http://localhost:5265` in a browser.

## Running on the LAN

To reach the app from other devices on the network:

1. In `email-job-backend/.env`, set:
   ```env
   HOST=0.0.0.0
   FRONTEND_ORIGIN=http://<lan-ip>:5265
   ```
   (`app.py` reads `HOST`, defaulting to `127.0.0.1` if unset.)
2. Start the backend as usual — Flask will print the LAN address it bound to.
3. Start the frontend with an explicit bind address so it isn't
   loopback-only:
   ```bash
   python3 -m http.server 5265 --bind 0.0.0.0
   ```
4. From another device, open `http://<lan-ip>:5265`.

The frontend's `app.js` builds its API base URL from the page's own
hostname (`window.location.hostname`), so it automatically talks to the
backend on whichever host served the page — no per-device config needed,
as long as `FRONTEND_ORIGIN` in `.env` matches that host for CORS.

## 4. Tests (optional)

```bash
cd email-job-backend
source .venv/bin/activate
python -m unittest -v
```

Backend tests don't send real email.
