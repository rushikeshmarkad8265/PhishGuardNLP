# PhishGuardNLP

PhishGuardNLP is a student-built Gmail security application that assigns explainable **Low**, **Medium**, or **High** risk tags to emails. It combines email text, sender metadata, links, and attachments in a transparent rule-based NLP scoring model inspired by the research paper *Risk-Level Tagging of Email Phishing Attacks Using NLP-Based Analysis of Emotional and Professional Impersonation Patterns*.

The project is designed as a preventive warning layer, not as a replacement for Gmail spam filtering or a trained machine-learning classifier.

## Highlights

- Connects to Gmail through OAuth 2.0 with read-only access.
- Scans messages in paginated batches of 15.
- Detects emotional pressure, urgency, secrecy, authority, finance, and compliance language.
- Checks sender-domain mismatches and SPF, DKIM, and DMARC authentication results.
- Evaluates insecure, shortened, IP-based, punycode, and misleading links.
- Raises risk for PDF, archive, macro, HTML, script, and executable attachments.
- Explains every risk score through matched indicators and phrases.
- Provides a Gmail-inspired responsive interface with a dedicated security panel.
- Lists all URLs detected in the selected email.
- Keeps OAuth credentials, tokens, and analysis history outside version control.

## Technology

| Layer | Technology |
| --- | --- |
| Backend | Python, Flask |
| Gmail integration | Gmail API, OAuth 2.0 |
| Frontend | HTML, CSS, JavaScript |
| Production server | Waitress |
| Testing | Python `unittest`, Flask test client |

## Architecture

```text
Gmail API
   |
   v
Message parser ----> Text + metadata + links + attachments
   |                                      |
   +------------------+-------------------+
                      v
             Explainable risk scoring
                      |
                      v
        Low / Medium / High + indicators
                      |
                      v
              Gmail-style web interface
```

## Run Locally

Requirements:

- Python 3.10 or newer
- A Google Cloud OAuth Desktop client

Install the dependencies:

```powershell
python -m pip install -r requirements.txt
```

Start the development server:

```powershell
python app.py
```

Open `http://127.0.0.1:5000`.

For a stable Windows server:

```powershell
python -m waitress --listen=127.0.0.1:5000 app:app
```

## Gmail API Setup

1. Create a project in Google Cloud Console.
2. Enable the Gmail API.
3. Configure the OAuth consent screen and add your Gmail account as a test user.
4. Create an OAuth Client ID with application type **Desktop app**.
5. Download the client file and rename it to `credentials.json`.
6. Place `credentials.json` in the project root.
7. Start PhishGuardNLP and select **Connect Gmail**.

The application requests only this scope:

```text
https://www.googleapis.com/auth/gmail.readonly
```

`credentials.json`, `token.json`, and `analysis_history.json` are ignored by Git and must never be committed.

## Tests

Run the automated test suite:

```powershell
python -m unittest discover -s tests -v
```

The tests cover low- and high-risk text, risky attachments, suspicious links, HTML email cleanup, the health endpoint, and the analysis API.

## Risk Model

The model uses weighted, interpretable rules rather than a trained machine-learning model. Multiple related indicators can reinforce one another and increase the final score. This makes each result traceable, but thresholds may require tuning for different organizations and languages.

## Privacy and Safety

- Gmail access is read-only; the app cannot send, delete, or modify messages.
- Email analysis runs in the local Flask application.
- OAuth files and local analysis history are excluded from GitHub.
- Links open in a new browser tab with `noopener` and `noreferrer` protection.

## Limitations

- Rule-based English-language analysis may miss novel or obfuscated phishing messages.
- A risk tag is a warning, not proof that an email is malicious.
- The project has not yet been benchmarked on a large labeled dataset.
- Gmail OAuth requires each deployment to configure its own Google Cloud credentials.

## Resume Summary

> Built a Flask-based Gmail security application that analyzes email content, metadata, links, and attachments to generate explainable phishing-risk tags. Integrated Gmail OAuth, paginated inbox scanning, and a responsive JavaScript interface while preserving read-only access and local credential privacy.

## Repository

[github.com/rushikeshmarkad8265/PhishGuardNLP](https://github.com/rushikeshmarkad8265/PhishGuardNLP)
