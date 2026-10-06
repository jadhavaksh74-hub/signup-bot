from flask import Flask, render_template, request, jsonify, send_file
import csv, io, os, time, uuid
from urllib.parse import urlparse
import requests

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

JOBS = {}

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; NewsletterSignupAssistant/1.0)"
}

def valid_url(url):
    try:
        p = urlparse(url.strip())
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False

def load_csv(file_storage):
    raw = file_storage.read()
    text = raw.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV must contain headers: brand,signup_url")

    fields = {f.strip().lower(): f for f in reader.fieldnames}
    if "brand" not in fields or "signup_url" not in fields:
        raise ValueError("CSV must contain columns named brand and signup_url")

    rows = []
    seen = set()
    for row in reader:
        brand = (row.get(fields["brand"]) or "").strip()
        url = (row.get(fields["signup_url"]) or "").strip()
        if not brand and not url:
            continue
        if not valid_url(url):
            rows.append({"brand": brand or "(unnamed)", "signup_url": url, "status": "Invalid URL"})
            continue
        key = url.lower().rstrip("/")
        if key in seen:
            rows.append({"brand": brand or "(unnamed)", "signup_url": url, "status": "Duplicate skipped"})
            continue
        seen.add(key)
        rows.append({"brand": brand or "(unnamed)", "signup_url": url, "status": "Queued"})
    return rows

def process_job(job_id, email):
    job = JOBS[job_id]
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)

    for item in job["rows"]:
        if job["stop"]:
            item["status"] = "Stopped"
            continue

        if item["status"] != "Queued":
            continue

        url = item["signup_url"]
        item["status"] = "Checking page..."
        job["current"] = item["brand"]
        try:
            r = session.get(url, timeout=15, allow_redirects=True)
            ct = r.headers.get("content-type", "")
            if r.status_code >= 400:
                item["status"] = f"Page unavailable (HTTP {r.status_code})"
            elif "text/html" not in ct.lower():
                item["status"] = "Not an HTML signup page"
            else:
                # We deliberately do not attempt to submit arbitrary forms.
                # This avoids guessing form fields and bypassing anti-bot controls.
                item["status"] = "Manual signup required"
                item["final_url"] = r.url
        except requests.RequestException as exc:
            item["status"] = "Connection failed"
            item["error"] = str(exc)[:160]

        time.sleep(0.25)

    job["done"] = True
    job["current"] = ""

@app.route("/")
def index():
    return render_template("index.html")

@app.post("/api/start")
def start():
    email = (request.form.get("email") or "").strip()
    upload = request.files.get("csv")

    if not email:
        return jsonify(error="Enter an email address."), 400
    if "@" not in email or "." not in email.split("@")[-1]:
        return jsonify(error="Enter a valid email address."), 400
    if not upload or not upload.filename.lower().endswith(".csv"):
        return jsonify(error="Upload a CSV file."), 400

    try:
        rows = load_csv(upload)
    except ValueError as e:
        return jsonify(error=str(e)), 400

    if not rows:
        return jsonify(error="The CSV contains no usable rows."), 400

    job_id = uuid.uuid4().hex
    JOBS[job_id] = {
        "email": email,
        "rows": rows,
        "stop": False,
        "done": False,
        "current": ""
    }

    import threading
    threading.Thread(target=process_job, args=(job_id, email), daemon=True).start()
    return jsonify(job_id=job_id, count=len(rows))

@app.get("/api/status/<job_id>")
def status(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify(error="Job not found."), 404
    return jsonify(
        done=job["done"],
        current=job["current"],
        rows=job["rows"]
    )

@app.post("/api/stop/<job_id>")
def stop(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify(error="Job not found."), 404
    job["stop"] = True
    return jsonify(ok=True)

@app.get("/api/export/<job_id>")
def export(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify(error="Job not found."), 404

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["brand", "signup_url", "status", "final_url", "error"],
        extrasaction="ignore"
    )
    writer.writeheader()
    writer.writerows(job["rows"])

    data = io.BytesIO(output.getvalue().encode("utf-8"))
    return send_file(
        data,
        mimetype="text/csv",
        as_attachment=True,
        download_name="subscription_results.csv"
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
