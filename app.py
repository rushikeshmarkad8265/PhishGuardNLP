from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

from flask import Flask, jsonify, render_template, request

from gmail_service import disconnect_account, build_gmail_service, get_profile, get_setup_status, link_domain, scan_messages


BASE_DIR = Path(__file__).resolve().parent
HISTORY_FILE = BASE_DIR / "analysis_history.json"


@dataclass(frozen=True)
class Indicator:
    category: str
    label: str
    weight: int
    patterns: tuple[str, ...]
    description: str


INDICATORS: tuple[Indicator, ...] = (
    Indicator(
        "Emotional",
        "Urgency and time pressure",
        16,
        ("urgent", "urgently", "immediately", "right now", "now", "as soon as possible", "asap"),
        "Pushes the reader to act before verifying the message.",
    ),
    Indicator(
        "Emotional",
        "Fear or distress appeal",
        20,
        ("in trouble", "serious trouble", "need money", "help me", "please help", "emergency", "stranded"),
        "Uses personal distress to exploit trust and empathy.",
    ),
    Indicator(
        "Emotional",
        "Secrecy request",
        22,
        ("don't tell anyone", "do not tell anyone", "keep this confidential", "keep it secret", "between us"),
        "Discourages normal verification or escalation.",
    ),
    Indicator(
        "Professional",
        "Financial context",
        18,
        ("invoice", "payment pending", "payroll", "bank account", "wire transfer", "refund", "salary"),
        "Introduces money, payroll, invoices, or account movement.",
    ),
    Indicator(
        "Professional",
        "Account verification",
        16,
        ("account verification", "verify your account", "confirm your account", "update your account", "login details"),
        "Requests account validation or credential-related action.",
    ),
    Indicator(
        "Professional",
        "Authority or department identity",
        14,
        ("hr department", "accounts team", "accounts department", "manager", "administrator", "it support", "security team"),
        "Claims institutional authority or procedural control.",
    ),
    Indicator(
        "Professional",
        "Compliance or punishment pressure",
        21,
        ("policy violation", "access suspension", "account suspended", "failure to", "will result in", "compliance"),
        "Uses penalties, compliance, or suspension to coerce action.",
    ),
    Indicator(
        "Professional",
        "Explicit deadline",
        16,
        ("within 24 hours", "within 12 hours", "before midnight", "today only", "deadline", "expires"),
        "Adds a time-bounded request that raises pressure.",
    ),
    Indicator(
        "Links",
        "Suspicious link or attachment language",
        13,
        ("click here", "open the attachment", "download the file", "secure link", "temporary link", "attached file"),
        "Encourages interaction with a link or attachment.",
    ),
)


CASE_STUDIES = [
    {
        "name": "Low-risk academic notice",
        "subject": "Assignment deadline update",
        "body": "Dear Students,\nPlease note that the assignment submission deadline has been extended to Friday.\nRegards,\nCourse Coordinator",
    },
    {
        "name": "Medium-risk payroll review",
        "subject": "Payroll detail review",
        "body": "Dear Employee,\nWe noticed an issue with your payroll details. Please review the information at your earliest convenience to avoid delays.",
    },
    {
        "name": "High-risk emotional impersonation",
        "subject": "Need help now",
        "body": "Hey, it's me. I'm in serious trouble and need money urgently. Please don't tell anyone, just help me now.",
    },
    {
        "name": "High-risk professional impersonation",
        "subject": "Account verification required",
        "body": "Dear Staff,\nFailure to verify your account within 12 hours will result in access suspension. Please complete the verification immediately.",
    },
]


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/samples")
    def samples():
        return jsonify(CASE_STUDIES)

    @app.post("/api/analyze")
    def analyze_email():
        payload = request.get_json(silent=True) or {}
        subject = str(payload.get("subject", ""))
        body = str(payload.get("body", ""))
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else None
        result = analyze(subject, body, metadata)
        append_history(result)
        return jsonify(result)

    @app.get("/api/gmail/status")
    def gmail_status():
        return jsonify(get_setup_status())

    @app.get("/api/gmail/profile")
    def gmail_profile():
        try:
            return jsonify({"ok": True, "profile": get_profile()})
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc), "status": get_setup_status()}), 400

    @app.post("/api/gmail/connect")
    def gmail_connect():
        try:
            build_gmail_service(force_auth=True)
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc), "status": get_setup_status()}), 400
        return jsonify({"ok": True, "status": get_setup_status()})

    @app.post("/api/gmail/disconnect")
    def gmail_disconnect():
        disconnect_account()
        return jsonify({"ok": True, "status": get_setup_status()})

    @app.get("/api/gmail/scan")
    def gmail_scan():
        try:
            limit = max(1, min(50, int(request.args.get("limit", 15))))
        except ValueError:
            limit = 15
        query = request.args.get("query", "in:anywhere")
        page_token = request.args.get("page_token") or None

        try:
            page = scan_messages(max_results=limit, query=query, page_token=page_token)
            results = []
            for message in page["messages"]:
                result = analyze(message["subject"], message["body"], message["metadata"])
                result["gmail_id"] = message["gmail_id"]
                result["thread_id"] = message["thread_id"]
                result["snippet"] = message["snippet"]
                result["from"] = message["headers"].get("from", "")
                result["date"] = message["headers"].get("date", "")
                result["body"] = message["body"]
                result["links"] = message["links"]
                result["attachments"] = message["attachments"]
                result["metadata"] = message["metadata"]
                results.append(result)
                append_history(result)
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc), "status": get_setup_status()}), 400

        return jsonify({
            "ok": True,
            "messages": results,
            "count": len(results),
            "next_page_token": page["next_page_token"],
            "result_size_estimate": page["result_size_estimate"],
        })

    @app.get("/api/history")
    def history():
        return jsonify(load_history()[-5:])

    @app.get("/api/health")
    def health():
        return jsonify({"ok": True, "service": "PhishGuard NLP Risk Tagger"})

    return app


def analyze(subject: str, body: str, metadata: dict | None = None) -> dict:
    text = normalize_text(f"{subject}\n{body}")
    words = re.findall(r"[a-z0-9']+", text)
    total_words = max(len(words), 1)

    matches = []
    raw_score = 0
    category_scores = {"Emotional": 0, "Professional": 0, "Links": 0, "Attachments": 0, "Metadata": 0}

    for indicator in INDICATORS:
        found = find_patterns(text, indicator.patterns)
        if not found:
            continue

        multiplier = min(1.8, 1 + (len(found) - 1) * 0.25)
        score = round(indicator.weight * multiplier)
        raw_score += score
        category_scores[indicator.category] += score
        matches.append(
            {
                "category": indicator.category,
                "label": indicator.label,
                "description": indicator.description,
                "weight": score,
                "phrases": found,
            }
        )

    pronoun_score, pronoun_detail = score_pronoun_targeting(words, total_words)
    if pronoun_score:
        raw_score += pronoun_score
        category_scores["Emotional"] += pronoun_score
        matches.append(pronoun_detail)

    metadata_score, metadata_matches = score_metadata(metadata or {}, text)
    raw_score += metadata_score
    for item in metadata_matches:
        category_scores[item["category"]] += item["weight"]
        matches.append(item)

    reinforcement_bonus = 0
    if category_scores["Attachments"] >= 35 or category_scores["Metadata"] >= 35:
        reinforcement_bonus = 15
    elif category_scores["Emotional"] >= 25 and category_scores["Professional"] >= 25:
        reinforcement_bonus = 15
    elif category_scores["Links"] >= 24 and (category_scores["Professional"] or category_scores["Emotional"]):
        reinforcement_bonus = 12
    elif len(matches) >= 3:
        reinforcement_bonus = 8

    raw_score += reinforcement_bonus
    score = min(100, raw_score)
    tag, guidance = assign_tag(score, matches, category_scores)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "subject": subject.strip(),
        "word_count": total_words,
        "risk_score": score,
        "risk_tag": tag,
        "guidance": guidance,
        "category_scores": category_scores,
        "reinforcement_bonus": reinforcement_bonus,
        "indicators": matches,
        "summary": build_summary(tag, matches, category_scores, reinforcement_bonus),
    }


def normalize_text(value: str) -> str:
    value = value.lower().replace("’", "'").replace("`", "'")
    return re.sub(r"\s+", " ", value).strip()


def find_patterns(text: str, patterns: Iterable[str]) -> list[str]:
    found = []
    for pattern in patterns:
        normalized = normalize_text(pattern)
        escaped = re.escape(normalized).replace(r"\ ", r"\s+")
        if re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", text):
            found.append(pattern)
    return found


def score_pronoun_targeting(words: list[str], total_words: int) -> tuple[int, dict | None]:
    personal_pronouns = {"i", "me", "my", "mine", "you", "your", "yours"}
    count = sum(1 for word in words if word in personal_pronouns)
    density = count / total_words
    if count < 5 and density < 0.12:
        return 0, None

    score = 10 if density < 0.18 else 15
    return score, {
        "category": "Emotional",
        "label": "Personal targeting language",
        "description": "High use of first-person or second-person pronouns can indicate direct trust exploitation.",
        "weight": score,
        "phrases": [f"{count} personal pronouns"],
    }


def score_metadata(metadata: dict, text: str) -> tuple[int, list[dict]]:
    matches: list[dict] = []
    total = 0

    attachment_score, attachment_matches = score_attachments(metadata.get("attachments", []))
    link_score, link_matches = score_links(metadata.get("links") or extract_links(text))
    header_score, header_matches = score_headers(metadata)

    for score, items in ((attachment_score, attachment_matches), (link_score, link_matches), (header_score, header_matches)):
        total += score
        matches.extend(items)

    return total, matches


def score_attachments(attachments: list[dict]) -> tuple[int, list[dict]]:
    dangerous = {".exe", ".scr", ".bat", ".cmd", ".com", ".js", ".vbs", ".ps1", ".msi", ".jar"}
    risky = {".pdf", ".docm", ".xlsm", ".pptm", ".zip", ".rar", ".7z", ".iso", ".html", ".htm"}
    matches = []
    total = 0

    for attachment in attachments:
        filename = str(attachment.get("filename", "attachment")).lower()
        suffix = Path(filename).suffix
        if suffix in dangerous:
            score = 45
            label = "Dangerous executable attachment"
            description = "Executable or script attachments can directly run code and are treated as high risk."
        elif suffix in risky:
            score = 18 if suffix == ".pdf" else 22
            label = "Risky attachment type"
            description = "PDFs, archives, macro documents, and HTML files are common phishing delivery formats."
        else:
            continue

        total += score
        matches.append(
            {
                "category": "Attachments",
                "label": label,
                "description": description,
                "weight": score,
                "phrases": [attachment.get("filename", "attachment")],
            }
        )

    return total, matches


def score_links(links: list[str]) -> tuple[int, list[dict]]:
    matches = []
    total = 0
    shorteners = {"bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd", "cutt.ly", "rebrand.ly"}

    if len(links) >= 4:
        total += 12
        matches.append(
            {
                "category": "Links",
                "label": "Multiple links",
                "description": "Messages with many links increase the chance of directing users to unsafe pages.",
                "weight": 12,
                "phrases": [f"{len(links)} links"],
            }
        )

    for link in links[:10]:
        domain = link_domain(link)
        parsed = urlparse(link)
        score = 0
        reasons = []

        if parsed.scheme.lower() != "https":
            score += 12
            reasons.append("non-HTTPS")
        if re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", domain):
            score += 24
            reasons.append("IP-address link")
        if domain.startswith("xn--"):
            score += 20
            reasons.append("punycode domain")
        if domain in shorteners:
            score += 18
            reasons.append("URL shortener")
        if "@" in link:
            score += 18
            reasons.append("misleading @ in URL")

        if score:
            total += score
            matches.append(
                {
                    "category": "Links",
                    "label": "Suspicious link",
                    "description": "The URL has properties often used to hide or disguise the destination.",
                    "weight": score,
                    "phrases": [f"{link} ({', '.join(reasons)})"],
                }
            )

    return total, matches


def score_headers(metadata: dict) -> tuple[int, list[dict]]:
    matches = []
    total = 0
    sender_domain = metadata.get("sender_domain", "")
    reply_to_domain = metadata.get("reply_to_domain", "")
    return_path_domain = metadata.get("return_path_domain", "")
    auth = str(metadata.get("authentication_results", "")).lower()

    if sender_domain and reply_to_domain and sender_domain != reply_to_domain:
        total += 18
        matches.append(
            {
                "category": "Metadata",
                "label": "Reply-To domain mismatch",
                "description": "The visible sender and reply destination use different domains.",
                "weight": 18,
                "phrases": [f"{sender_domain} -> {reply_to_domain}"],
            }
        )

    if sender_domain and return_path_domain and sender_domain != return_path_domain:
        total += 14
        matches.append(
            {
                "category": "Metadata",
                "label": "Return-Path domain mismatch",
                "description": "The delivery return path differs from the visible sender domain.",
                "weight": 14,
                "phrases": [f"{sender_domain} -> {return_path_domain}"],
            }
        )

    failed = [name for name in ("spf", "dkim", "dmarc") if re.search(rf"{name}=(fail|softfail|neutral|temperror|permerror)", auth)]
    if failed:
        score = 24 if "dmarc" in failed else 16
        total += score
        matches.append(
            {
                "category": "Metadata",
                "label": "Email authentication warning",
                "description": "SPF, DKIM, or DMARC did not pass cleanly in the Gmail authentication header.",
                "weight": score,
                "phrases": failed,
            }
        )

    return total, matches


def assign_tag(score: int, matches: list[dict], category_scores: dict[str, int]) -> tuple[str, str]:
    has_secrecy = any(item["label"] == "Secrecy request" for item in matches)
    has_compliance = any(item["label"] == "Compliance or punishment pressure" for item in matches)
    has_deadline = any(item["label"] == "Explicit deadline" for item in matches)

    has_executable = any(item["label"] == "Dangerous executable attachment" for item in matches)
    has_auth_warning = any(item["label"] == "Email authentication warning" for item in matches)

    if score >= 60 or has_executable or (has_auth_warning and score >= 35) or (has_secrecy and score >= 45) or (has_compliance and has_deadline):
        return "High", "Do not click links, open attachments, or send information. Verify through a trusted channel."
    if score >= 28 or category_scores["Attachments"] or category_scores["Links"] >= 12 or category_scores["Professional"] >= 18 or category_scores["Emotional"] >= 20:
        return "Medium", "Pause and verify the sender, request, and any links before responding."
    return "Low", "No strong impersonation pattern was found. Normal caution is still recommended."


def build_summary(tag: str, matches: list[dict], category_scores: dict[str, int], bonus: int) -> str:
    if not matches:
        return "The email uses mostly neutral language with no major emotional or professional impersonation cues."

    strongest = sorted(matches, key=lambda item: item["weight"], reverse=True)[:3]
    labels = ", ".join(item["label"].lower() for item in strongest)
    dominant = max(category_scores, key=category_scores.get)
    extra = " Combined cues increased the score." if bonus else ""
    return f"{tag} risk is driven mainly by {dominant.lower()} indicators: {labels}.{extra}"


def append_history(result: dict) -> None:
    history = load_history()
    entry = {
        "timestamp": result["timestamp"],
        "gmail_id": result.get("gmail_id"),
        "subject": result["subject"] or "(No subject)",
        "risk_score": result["risk_score"],
        "risk_tag": result["risk_tag"],
    }

    if entry["gmail_id"]:
        history = [item for item in history if item.get("gmail_id") != entry["gmail_id"]]

    history.append(entry)
    HISTORY_FILE.write_text(json.dumps(history[-5:], indent=2), encoding="utf-8")


def load_history() -> list[dict]:
    if not HISTORY_FILE.exists():
        return []
    try:
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def extract_links(text: str) -> list[str]:
    links = re.findall(r"https?://[^\s<>'\")]+", text, flags=re.IGNORECASE)
    return [link.rstrip(".,;:!?]") for link in links]


app = create_app()


if __name__ == "__main__":
    app.run(debug=False, port=5000, use_reloader=False)
