# Newsletter Signup Assistant

Open in GitHub Codespaces, then run `python -m pip install -r requirements.txt` and `python app.py`. Open forwarded port 5000.

Test: `curl http://127.0.0.1:5000/health` should return `{"status":"ok"}`.

CSV headers: `brand,signup_url`.

The app does not bypass CAPTCHA, Cloudflare, consent gates, rate limits, or other anti-bot protections.
