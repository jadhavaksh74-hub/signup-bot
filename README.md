# Newsletter Signup Assistant — GitHub Codespaces

A small Flask browser app for checking newsletter signup URLs from a CSV.

## CSV format

Create a CSV such as:

```csv
brand,signup_url
Example Brand,https://example.com/newsletter
Another Brand,https://example.org/subscribe
```

## Run in GitHub Codespaces

1. Create a new GitHub repository.
2. Upload this project.
3. Open the repository in **Codespaces**.
4. In the Codespaces terminal run:

```bash
pip install -r requirements.txt
python app.py
```

5. When Codespaces detects port `5000`, open the forwarded port in the browser.

## What it does

- Validates the CSV.
- Removes duplicate signup URLs.
- Checks each URL sequentially.
- Reports HTTP failures and non-HTML pages.
- Marks reachable signup pages as **Manual signup required**.
- Exports the results as CSV.

## Safety / anti-bot behavior

This version intentionally does not automate arbitrary form submissions or attempt to bypass CAPTCHA, Cloudflare, consent requirements, rate limits, or other anti-bot controls. Newsletter providers can have different forms and terms, so the app leaves the actual signup action to the user.

## Important

Do not commit passwords, API keys, SMTP credentials, or private email credentials to GitHub. The email entered in this app is only used as the value shown to the local job; this version does not send or store mail credentials.
