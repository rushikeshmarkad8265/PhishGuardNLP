# PhishGuard NLP Risk Tagger

GUI application based on the draft paper, "Risk-Level Tagging of Email Phishing Attacks Using NLP-Based Analysis of Emotional and Professional Impersonation Patterns."

The app runs locally with a Python Flask backend and an HTML/CSS/JavaScript frontend. It analyzes subject and body text, assigns Low, Medium, or High risk, and explains the emotional, professional, and technical indicators that contributed to the score.

## Run

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

```powershell
python app.py
```

For a stable background server on Windows:

```powershell
python -m waitress --listen=127.0.0.1:5000 app:app
```

Open:

```text
http://127.0.0.1:5000
```

## Features

- NLP-inspired weighted scoring for emotional impersonation cues.
- Professional impersonation scoring for finance, authority, compliance, and deadlines.
- Gmail API read-only inbox scanning.
- Connected Gmail account summary with mailbox counts.
- Live inbox polling for recent messages.
- Metadata checks for sender/reply-to/return-path mismatch and SPF, DKIM, or DMARC warnings.
- Link checks for non-HTTPS URLs, IP-address links, shorteners, punycode domains, and misleading `@` URLs.
- Attachment checks that raise risk for `.pdf`, archives, macro documents, HTML files, and mark executables such as `.exe` as high risk.
- Risk-level tags instead of binary phishing classification.
- Indicator-level explanation with matched phrases.
- Paper-based case study samples.
- Local recent-analysis history in `analysis_history.json`.

## Gmail API Setup

1. Create a Google Cloud project.
2. Enable the Gmail API.
3. Configure the OAuth consent screen.
4. Create an OAuth Client ID for a Desktop app.
5. Download the client file, rename it to `credentials.json`, and keep it in the project root.
6. Start the app and click `Connect Gmail`.

Do not commit `credentials.json` or `token.json`. They are ignored by `.gitignore`.

The app requests only:

```text
https://www.googleapis.com/auth/gmail.readonly
```

## Reply Support

Replying from this app is possible with the Gmail API, but it is intentionally not enabled in this version. Sending replies requires broader Gmail permissions such as `gmail.send`, MIME message construction, and correct `threadId`, `In-Reply-To`, and `References` headers. This project stays read-only so it is safer to demo, review, and publish.
