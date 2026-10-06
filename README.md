
# Newsletter Subscription Tool — Browser Version

Runs as a small Flask web app in GitHub Codespaces.

## CSV format

Your CSV must have these headers:

```csv
brand,signup_url
Example Brand,https://example.com/newsletter
```

## Codespaces setup

In the Codespaces terminal:

```bash
pip install -r requirements.txt
python -m playwright install --with-deps chromium
python app.py
```

Then open port **8000** in the Codespaces Ports panel.

## Important behavior

- Uses only the email address you enter.
- Uses only signup URLs supplied in your CSV.
- Runs Chromium visibly only in the original desktop app; this browser version uses headless Chromium because Codespaces has no desktop display.
- Does not bypass CAPTCHA, Cloudflare, anti-bot checks, access controls, or email verification.
- A detected challenge is recorded as `manual_review`.
- `submitted` means the form was submitted; it does not guarantee that the site accepted the subscription or that a confirmation email was received.
- Use only with brands/sites where you are permitted to subscribe and with an email address you control.
