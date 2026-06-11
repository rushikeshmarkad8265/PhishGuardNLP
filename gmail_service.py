from __future__ import annotations

import base64
import re
from email.utils import parseaddr
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


BASE_DIR = Path(__file__).resolve().parent
CREDENTIALS_FILE = BASE_DIR / "credentials.json"
TOKEN_FILE = BASE_DIR / "token.json"
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def gmail_dependencies_available() -> bool:
    try:
        import google.auth.transport.requests  # noqa: F401
        import google.oauth2.credentials  # noqa: F401
        import google_auth_oauthlib.flow  # noqa: F401
        import googleapiclient.discovery  # noqa: F401
    except ImportError:
        return False
    return True


def get_setup_status() -> dict[str, Any]:
    return {
        "dependencies": gmail_dependencies_available(),
        "credentials_file": CREDENTIALS_FILE.exists(),
        "token_file": TOKEN_FILE.exists(),
        "connected": TOKEN_FILE.exists() and gmail_dependencies_available(),
        "scope": SCOPES[0],
    }


def get_profile() -> dict[str, Any]:
    service = build_gmail_service()
    profile = service.users().getProfile(userId="me").execute()
    email = profile.get("emailAddress", "")
    return {
        "email": email,
        "initial": email[:1].upper() if email else "G",
        "messages_total": profile.get("messagesTotal", 0),
        "threads_total": profile.get("threadsTotal", 0),
        "history_id": profile.get("historyId", ""),
    }


def disconnect_account() -> None:
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()


def build_gmail_service(force_auth: bool = False):
    if not gmail_dependencies_available():
        raise RuntimeError("Missing Gmail API packages. Run: pip install -r requirements.txt")
    if not CREDENTIALS_FILE.exists():
        raise RuntimeError("Missing credentials.json. Download an OAuth desktop client from Google Cloud and place it in this folder.")

    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if TOKEN_FILE.exists() and not force_auth:
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token and not force_auth:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")

    return build("gmail", "v1", credentials=creds)


def scan_messages(max_results: int = 10, query: str = "newer_than:30d", page_token: str | None = None) -> dict[str, Any]:
    service = build_gmail_service()
    scanned = []
    request = {
        "userId": "me",
        "maxResults": max_results,
    }
    if query:
        request["q"] = query
    if page_token:
        request["pageToken"] = page_token

    response = service.users().messages().list(**request).execute()
    for item in response.get("messages", []):
        message = service.users().messages().get(userId="me", id=item["id"], format="full").execute()
        scanned.append(parse_message(message))

    return {
        "messages": scanned,
        "next_page_token": response.get("nextPageToken"),
        "result_size_estimate": response.get("resultSizeEstimate", 0),
    }


def parse_message(message: dict[str, Any]) -> dict[str, Any]:
    payload = message.get("payload", {})
    headers = header_map(payload.get("headers", []))
    body_parts: list[str] = []
    attachments: list[dict[str, Any]] = []

    collect_parts(payload, body_parts, attachments)
    body = "\n".join(part for part in body_parts if part).strip()
    links = extract_links(f"{headers.get('subject', '')}\n{body}")

    return {
        "gmail_id": message.get("id"),
        "thread_id": message.get("threadId"),
        "snippet": message.get("snippet", ""),
        "subject": headers.get("subject", "(No subject)"),
        "body": body or message.get("snippet", ""),
        "headers": headers,
        "links": links,
        "attachments": attachments,
        "metadata": build_metadata(headers, links, attachments),
    }


def header_map(headers: list[dict[str, str]]) -> dict[str, str]:
    result = {}
    for header in headers:
        name = header.get("name", "").lower()
        value = header.get("value", "")
        if name:
            result[name] = value
    return result


def collect_parts(part: dict[str, Any], body_parts: list[str], attachments: list[dict[str, Any]]) -> None:
    filename = part.get("filename") or ""
    body = part.get("body", {})
    mime_type = part.get("mimeType", "")

    if filename:
        attachments.append(
            {
                "filename": filename,
                "mime_type": mime_type,
                "size": body.get("size", 0),
                "attachment_id": body.get("attachmentId"),
            }
        )

    data = body.get("data")
    if data and mime_type in {"text/plain", "text/html"}:
        decoded = decode_body(data)
        if mime_type == "text/html":
            decoded = re.sub(r"<[^>]+>", " ", decoded)
        body_parts.append(decoded)

    for child in part.get("parts", []) or []:
        collect_parts(child, body_parts, attachments)


def decode_body(data: str) -> str:
    try:
        padded = data + "=" * (-len(data) % 4)
        return base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8", errors="replace")
    except Exception:
        return ""


def extract_links(text: str) -> list[str]:
    links = re.findall(r"https?://[^\s<>'\")]+", text, flags=re.IGNORECASE)
    normalized = []
    for link in links:
        cleaned = link.rstrip(".,;:!?]")
        if cleaned not in normalized:
            normalized.append(cleaned)
    return normalized[:25]


def build_metadata(headers: dict[str, str], links: list[str], attachments: list[dict[str, Any]]) -> dict[str, Any]:
    from_email = parseaddr(headers.get("from", ""))[1]
    reply_to = parseaddr(headers.get("reply-to", ""))[1]
    return_path = parseaddr(headers.get("return-path", ""))[1].strip("<>")

    return {
        "from": headers.get("from", ""),
        "from_email": from_email,
        "reply_to": headers.get("reply-to", ""),
        "return_path": headers.get("return-path", ""),
        "authentication_results": headers.get("authentication-results", ""),
        "sender_domain": email_domain(from_email),
        "reply_to_domain": email_domain(reply_to),
        "return_path_domain": email_domain(return_path),
        "links": links,
        "attachments": attachments,
    }


def email_domain(value: str) -> str:
    if "@" not in value:
        return ""
    return value.rsplit("@", 1)[1].lower()


def link_domain(url: str) -> str:
    return urlparse(url).netloc.lower().split("@")[-1].split(":")[0]
