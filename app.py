
import asyncio
import csv
import io
import re
import threading
from pathlib import Path
from flask import Flask, jsonify, render_template, request, send_file
from playwright.async_api import async_playwright

app = Flask(__name__)

jobs = {}
job_counter = 0
lock = threading.Lock()

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def challenge_text(text):
    t = (text or "").lower()
    words = [
        "captcha", "recaptcha", "hcaptcha", "cloudflare",
        "verify you are human", "checking your browser",
        "security challenge", "access denied"
    ]
    return any(w in t for w in words)

async def find_email_input(page):
    selectors = [
        'input[type="email"]',
        'input[name*="email" i]',
        'input[id*="email" i]',
        'input[placeholder*="email" i]',
    ]
    for selector in selectors:
        try:
            el = page.locator(selector).first
            if await el.count() and await el.is_visible():
                return el
        except Exception:
            pass
    return None

async def subscribe_one(page, brand, url, email):
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(1200)

        body = await page.locator("body").inner_text(timeout=5000)
        if challenge_text(body):
            return "manual_review", "CAPTCHA/anti-bot challenge detected"

        field = await find_email_input(page)
        if not field:
            return "failed", "No visible email field found"

        await field.fill(email)

        # Prefer a nearby newsletter/subscribe button, then common submit controls.
        candidates = [
            'button:has-text("Subscribe")',
            'button:has-text("Sign up")',
            'button:has-text("Join")',
            'input[type="submit"]',
            'button[type="submit"]',
        ]
        clicked = False
        for selector in candidates:
            try:
                btn = page.locator(selector).first
                if await btn.count() and await btn.is_visible() and await btn.is_enabled():
                    await btn.click()
                    clicked = True
                    break
            except Exception:
                pass

        if not clicked:
            await field.press("Enter")

        await page.wait_for_timeout(1800)
        after = await page.locator("body").inner_text(timeout=5000)
        if challenge_text(after):
            return "manual_review", "Challenge appeared after submission"

        return "submitted", "Form submitted; check inbox if confirmation is required"
    except Exception as e:
        return "failed", str(e)[:300]

async def run_job(job_id, rows, email):
    results = []
    jobs[job_id]["status"] = "running"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        for i, row in enumerate(rows):
            if jobs[job_id].get("stop"):
                jobs[job_id]["status"] = "stopped"
                break

            brand = row["brand"].strip()
            url = row["signup_url"].strip()
            status, message = await subscribe_one(page, brand, url, email)
            results.append({
                "brand": brand,
                "signup_url": url,
                "status": status,
                "message": message,
            })
            jobs[job_id]["current"] = i + 1
            jobs[job_id]["results"] = results
            await asyncio.sleep(1.5)

        await browser.close()

    if jobs[job_id]["status"] == "running":
        jobs[job_id]["status"] = "completed"

@app.route("/")
def index():
    return render_template("index.html")

@app.post("/start")
def start():
    global job_counter
    email = request.form.get("email", "").strip()
    file = request.files.get("csv")
    if not EMAIL_RE.match(email):
        return jsonify(error="Enter a valid email address."), 400
    if not file:
        return jsonify(error="Upload a CSV file."), 400

    try:
        text = file.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames or "brand" not in reader.fieldnames or "signup_url" not in reader.fieldnames:
            return jsonify(error="CSV must contain exactly these required headers: brand, signup_url"), 400

        rows = []
        seen = set()
        for r in reader:
            brand = (r.get("brand") or "").strip()
            url = (r.get("signup_url") or "").strip()
            if not brand or not url or url in seen:
                continue
            if not re.match(r"^https?://", url, re.I):
                continue
            seen.add(url)
            rows.append({"brand": brand, "signup_url": url})

        if not rows:
            return jsonify(error="No valid rows found."), 400

        with lock:
            job_counter += 1
            job_id = str(job_counter)
            jobs[job_id] = {
                "status": "queued", "total": len(rows), "current": 0,
                "results": [], "stop": False
            }

        threading.Thread(
            target=lambda: asyncio.run(run_job(job_id, rows, email)),
            daemon=True
        ).start()
        return jsonify(job_id=job_id)
    except Exception as e:
        return jsonify(error=str(e)), 400

@app.get("/status/<job_id>")
def status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify(error="Job not found"), 404
    return jsonify(job)

@app.post("/stop/<job_id>")
def stop(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify(error="Job not found"), 404
    job["stop"] = True
    return jsonify(ok=True)

@app.get("/download/<job_id>")
def download(job_id):
    job = jobs.get(job_id)
    if not job:
        return "Job not found", 404
    output = io.StringIO()
    fields = ["brand", "signup_url", "status", "message"]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    writer.writerows(job.get("results", []))
    data = io.BytesIO(output.getvalue().encode("utf-8"))
    return send_file(data, mimetype="text/csv", as_attachment=True,
                     download_name="subscription_results.csv")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
