import csv
import io
import os
import re
import smtplib
import ssl
import threading
import uuid
from datetime import datetime, timezone
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 12 * 1024 * 1024

JOBS = {}
JOBS_LOCK = threading.Lock()
REQUIRED_COLUMNS = {"first_name", "last_name", "email"}
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
TOKEN_RE = re.compile(r"{{\s*(first_name|name|event)\s*}}", re.IGNORECASE)

DEFAULT_TEMPLATE = {
    "template_name": "Vibezone welcome",
    "event": "",
    "subject": "Registration confirmed for {{event}}",
    "preheader": "Your event registration is confirmed.",
    "heading": "THANKS",
    "message_html": (
        "<p>Hello {{first_name}},</p>"
        "<p>We are delighted to have you with us and appreciate the time you took to register.</p>"
        "<p>We look forward to welcoming you and hope you have a memorable experience.</p>"
        "<p>If you have any questions or need additional information, please don't hesitate to contact us.</p>"
        "<p>See you soon!</p><p>Kind regards,<br>The Vibezone</p>"
    ),
    "button_text": "Get started",
    "accent": "#3046d3",
    "button_url": "",
    "logo_url": "",
    "footer": "WeGatherEvents · Event Operations",
}


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = os.getenv("FRONTEND_ORIGIN", "*")
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def template_from_form():
    payload = request.form.to_dict() if request.form else (request.get_json(silent=True) or {})
    return {**DEFAULT_TEMPLATE, **{key: value for key, value in payload.items() if key in DEFAULT_TEMPLATE}}


def validate_logo(logo):
    if not logo:
        return None, None
    if logo.mimetype not in {"image/png", "image/jpeg", "image/gif"}:
        raise ValueError("Custom logos must be PNG, JPG, or GIF images.")
    data = logo.read()
    if len(data) > 3 * 1024 * 1024:
        raise ValueError("Custom logos must be no larger than 3 MB.")
    return data, logo.mimetype


def personalize(value, name, event, first_name=None):
    replacements = {"name": name, "first_name": first_name or name.split()[0], "event": event}
    return TOKEN_RE.sub(lambda match: replacements[match.group(1).lower()], value or "")


def render_email(template, name="Jordan Lee", first_name=None):
    template = {**DEFAULT_TEMPLATE, **template}
    event = template.get("event", "") or "Your event"
    values = {key: personalize(str(value), name, event, first_name) for key, value in template.items()}
    accent = values["accent"] if re.fullmatch(r"#[0-9a-fA-F]{6}", values["accent"]) else "#635bff"
    logo = ""
    if values["logo_url"]:
        logo = f'<img src="{values["logo_url"]}" alt="Logo" style="max-height:48px;max-width:180px;margin-bottom:28px">'
    button = ""
    if values["button_text"]:
        button_url = values["button_url"] or "#"
        button = (
            f'<p style="margin:30px 0"><a href="{button_url}" '
            f'style="background:{accent};color:#fff;text-decoration:none;padding:14px 46px;'
            f'border-radius:4px;font-weight:700;display:inline-block">{values["button_text"]}</a></p>'
        )
    html = f'''<!doctype html><html><body style="margin:0;background:#f1f1f1;font-family:Arial,sans-serif;color:#353535">
    <div style="display:none;max-height:0;overflow:hidden">{values['preheader']}</div>
    <div style="max-width:620px;margin:24px auto;background:#fff;overflow:hidden;box-shadow:0 8px 30px rgba(0,0,0,.08)">
      <div style="background:{accent};color:#fff;text-align:center;padding:46px 30px 38px">{logo}
        <h1 style="font-size:54px;line-height:1;margin:10px 0 5px;letter-spacing:1px">{values['heading']}</h1>
        <div style="font-size:25px">for joining us!</div>
      </div>
      <div style="padding:38px 44px 28px"><div style="font-size:16px;line-height:1.65">{values['message_html']}</div>
      <div style="text-align:center">{button}</div></div>
      <div style="padding:20px 42px;text-align:center;color:#747789;font-size:13px">{values['footer']}</div>
    </div></body></html>'''
    return values["subject"], html


def parse_csv(file_storage):
    if not file_storage or not file_storage.filename.lower().endswith(".csv"):
        raise ValueError("Upload a CSV file.")
    text = file_storage.stream.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    columns = set(reader.fieldnames or [])
    missing = REQUIRED_COLUMNS - columns
    if missing:
        raise ValueError(f"Missing CSV columns: {', '.join(sorted(missing))}.")
    recipients = []
    errors = []
    for line, row in enumerate(reader, start=2):
        email = (row.get("email") or "").strip()
        first = (row.get("first_name") or "").strip()
        last = (row.get("last_name") or "").strip()
        if not EMAIL_RE.match(email):
            errors.append(f"Row {line}: invalid email address.")
            continue
        recipients.append({"first_name": first or "Guest", "name": " ".join(part for part in (first, last) if part) or "Guest", "email": email})
    if not recipients:
        raise ValueError("The CSV does not contain any valid recipients.")
    return recipients, errors


def attach_logo(message, logo_data, logo_type):
    if not logo_data:
        return
    subtype = (logo_type or "image/png").split("/")[-1]
    image = MIMEImage(logo_data, _subtype=subtype)
    image.add_header("Content-ID", "<custom-logo>")
    image.add_header("Content-Disposition", "inline", filename=f"logo.{subtype}")
    message.attach(image)


def send_message(recipient, template, logo_data=None, logo_type=None):
    server_name = os.getenv("SMTP_SERVER")
    username = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    if not all((server_name, username, password)):
        raise RuntimeError("SMTP_SERVER, SMTP_USER, and SMTP_PASSWORD must be configured.")
    subject, html = render_email(template, recipient["name"], recipient.get("first_name"))
    if logo_data:
        html = html.replace(template.get("logo_url", ""), "cid:custom-logo") if template.get("logo_url") else html.replace(
            '<h1 style="font-size:30px', '<img src="cid:custom-logo" alt="Logo" style="max-height:48px;max-width:180px;margin-bottom:28px"><h1 style="font-size:30px'
        )
    message = MIMEMultipart("related")
    message["From"] = os.getenv("SMTP_FROM", username)
    message["To"] = recipient["email"]
    message["Subject"] = subject
    alternative = MIMEMultipart("alternative")
    alternative.attach(MIMEText("This message requires an HTML-capable email client.", "plain"))
    alternative.attach(MIMEText(html, "html"))
    message.attach(alternative)
    attach_logo(message, logo_data, logo_type)
    port = int(os.getenv("SMTP_PORT", "465"))
    with smtplib.SMTP_SSL(server_name, port, context=ssl.create_default_context(), timeout=30) as server:
        server.login(username, password)
        server.send_message(message)


def execute_job(job_id, recipients, template, logo_data, logo_type):
    with JOBS_LOCK:
        JOBS[job_id]["status"] = "running"
    for recipient in recipients:
        try:
            send_message(recipient, template, logo_data, logo_type)
            with JOBS_LOCK:
                JOBS[job_id]["sent"] += 1
        except Exception as exc:
            with JOBS_LOCK:
                JOBS[job_id]["failed"] += 1
                JOBS[job_id]["errors"].append(f'{recipient["email"]}: {exc}')
        with JOBS_LOCK:
            JOBS[job_id]["processed"] += 1
    with JOBS_LOCK:
        JOBS[job_id]["status"] = "completed"
        JOBS[job_id]["finished_at"] = utc_now()


@app.get("/api/health")
def health():
    return jsonify(status="ok", smtp_configured=all(os.getenv(key) for key in ("SMTP_SERVER", "SMTP_USER", "SMTP_PASSWORD")))


@app.post("/api/preview")
def preview():
    template = template_from_form()
    subject, html = render_email(template, request.form.get("preview_name", "Jordan Lee") if request.form else "Jordan Lee")
    return jsonify(subject=subject, html=html)


@app.post("/api/recipients/validate")
def validate_recipients():
    try:
        recipients, errors = parse_csv(request.files.get("csv"))
        return jsonify(count=len(recipients), errors=errors, sample=recipients[:5])
    except (ValueError, UnicodeDecodeError) as exc:
        return jsonify(error=str(exc)), 400


@app.post("/api/send-test")
def send_test():
    email = request.form.get("test_email", "").strip()
    if not EMAIL_RE.match(email):
        return jsonify(error="Enter a valid test recipient email."), 400
    try:
        logo = request.files.get("logo")
        logo_data, logo_type = validate_logo(logo)
        send_message({"name": "Test Recipient", "email": email}, template_from_form(), logo_data, logo_type)
        return jsonify(message=f"Test email sent to {email}.")
    except Exception as exc:
        return jsonify(error=str(exc)), 502


@app.post("/api/jobs")
def create_job():
    try:
        recipients, validation_errors = parse_csv(request.files.get("csv"))
    except (ValueError, UnicodeDecodeError) as exc:
        return jsonify(error=str(exc)), 400
    logo = request.files.get("logo")
    try:
        logo_data, logo_type = validate_logo(logo)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    job_id = uuid.uuid4().hex
    job = {"id": job_id, "status": "queued", "total": len(recipients), "processed": 0, "sent": 0, "failed": 0,
           "errors": validation_errors, "created_at": utc_now(), "finished_at": None}
    with JOBS_LOCK:
        JOBS[job_id] = job
    threading.Thread(target=execute_job, args=(job_id, recipients, template_from_form(), logo_data, logo_type), daemon=True).start()
    return jsonify(job), 202


@app.get("/api/jobs/<job_id>")
def get_job(job_id):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        return (jsonify(job), 200) if job else (jsonify(error="Job not found."), 404)


if __name__ == "__main__":
    app.run(host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "5000")), debug=os.getenv("FLASK_DEBUG") == "1")
