const form = document.querySelector("#email-form");
const subjectInput = document.querySelector("#subject");
const bodyInput = document.querySelector("#body");
const clearBtn = document.querySelector("#clear-btn");
const sampleList = document.querySelector("#sample-list");
const historyList = document.querySelector("#history-list");
const gmailStatus = document.querySelector("#gmail-status");
const connectGmailBtn = document.querySelector("#connect-gmail-btn");
const scanGmailBtn = document.querySelector("#scan-gmail-btn");
const connectAnotherBtn = document.querySelector("#connect-another-btn");
const gmailQuery = document.querySelector("#gmail-query");
const gmailLimit = document.querySelector("#gmail-limit");
const gmailResults = document.querySelector("#gmail-results");
const moreMailsBtn = document.querySelector("#more-mails-btn");
const mailReader = document.querySelector("#mail-reader");
const riskBand = document.querySelector("#risk-band");
const riskTag = document.querySelector("#risk-tag");
const riskScore = document.querySelector("#risk-score");
const guidance = document.querySelector("#guidance");
const summary = document.querySelector("#summary");
const indicatorList = document.querySelector("#indicator-list");
const accountAvatar = document.querySelector("#account-avatar");
const accountEmail = document.querySelector("#account-email");
const accountMeta = document.querySelector("#account-meta");
const mailCount = document.querySelector("#mail-count");
const highCount = document.querySelector("#high-count");
const mediumCount = document.querySelector("#medium-count");
const lowCount = document.querySelector("#low-count");

const metricIds = {
  Emotional: document.querySelector("#emotional-score"),
  Professional: document.querySelector("#professional-score"),
  Links: document.querySelector("#links-score"),
  Attachments: document.querySelector("#attachments-score"),
  Metadata: document.querySelector("#metadata-score"),
};

const wordCount = document.querySelector("#word-count");
let gmailMessages = [];
let selectedGmailId = "";
let scanInProgress = false;
let nextPageToken = "";

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  await analyzeEmail();
});

clearBtn.addEventListener("click", () => {
  subjectInput.value = "";
  bodyInput.value = "";
  resetResults();
});

connectGmailBtn.addEventListener("click", async () => {
  await connectGmail();
});

async function connectGmail() {
  setGmailBusy(true, "Connecting...");
  try {
    const response = await fetch("/api/gmail/connect", { method: "POST" });
    const data = await response.json();
    if (!data.ok) {
      renderGmailStatus(data.status, data.error);
      return;
    }
    renderGmailStatus(data.status);
    await loadGmailProfile();
    await resetAndScan();
  } catch (error) {
    await loadGmailStatus();
    gmailStatus.textContent = `${gmailStatus.textContent} Connection could not start from the browser.`;
  } finally {
    setGmailBusy(false);
  }
}

scanGmailBtn.addEventListener("click", async () => {
  await resetAndScan();
});

connectAnotherBtn.addEventListener("click", async () => {
  setGmailBusy(true, "Switching...");
  try {
    await fetch("/api/gmail/disconnect", { method: "POST" });
    gmailMessages = [];
    nextPageToken = "";
    selectedGmailId = "";
    renderGmailResults([]);
    renderScanOverview();
    collapseSelectedMail();
    await connectGmail();
  } finally {
    setGmailBusy(false);
  }
});

moreMailsBtn.addEventListener("click", async () => {
  if (!nextPageToken) return;
  await scanGmail({ append: true, selectFirst: false });
});

async function resetAndScan() {
  gmailMessages = [];
  nextPageToken = "";
  selectedGmailId = "";
  collapseSelectedMail();
  await scanGmail({ append: false, selectFirst: true });
}

async function analyzeEmail() {
  const subject = subjectInput.value.trim();
  const body = bodyInput.value.trim();

  if (!subject && !body) {
    guidance.textContent = "Enter a subject or body before analysis.";
    return;
  }

  setBusy(true);
  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ subject, body }),
    });
    const result = await response.json();
    renderResult(result);
    await loadHistory();
  } catch (error) {
    guidance.textContent = "The backend did not respond. Check that Flask is running.";
  } finally {
    setBusy(false);
  }
}

async function scanGmail(options = {}) {
  const append = Boolean(options.append);
  const selectFirst = options.selectFirst !== false;
  if (scanInProgress) return;

  scanInProgress = true;
  setGmailBusy(true, append ? "Loading..." : "Scanning...");
  if (!append) {
    gmailResults.className = "gmail-results empty";
  }

  const query = gmailQuery.value.trim() || "in:anywhere";
  const params = new URLSearchParams({
    query,
    limit: gmailLimit.value || "15",
  });
  if (append && nextPageToken) {
    params.set("page_token", nextPageToken);
  }

  try {
    const response = await fetch(`/api/gmail/scan?${params.toString()}`);
    const data = await response.json();
    if (!data.ok) {
      renderGmailStatus(data.status, data.error);
      gmailResults.textContent = data.error || "Gmail scan failed.";
      return;
    }
    mergeGmailMessages(data.messages);
    nextPageToken = data.next_page_token || "";
    renderGmailResults(gmailMessages);
    renderScanOverview();
    if (selectFirst && gmailMessages.length && !selectedGmailId) {
      openSelectedMail(gmailMessages[0]);
    }
    updateMoreButton();
    await loadHistory();
  } catch (error) {
    gmailResults.textContent = "Gmail scan failed. Check that the server is running.";
  } finally {
    scanInProgress = false;
    setGmailBusy(false);
  }
}

function mergeGmailMessages(messages) {
  let newCount = 0;
  const existing = new Map(gmailMessages.map((message) => [message.gmail_id || message.subject, message]));

  messages.forEach((message) => {
    const key = message.gmail_id || message.subject;
    if (!existing.has(key)) {
      newCount += 1;
    }
    existing.set(key, message);
  });

  gmailMessages = Array.from(existing.values()).sort((a, b) => {
    const aTime = Date.parse(a.date || a.timestamp || "") || 0;
    const bTime = Date.parse(b.date || b.timestamp || "") || 0;
    return bTime - aTime;
  });

  return newCount;
}

function updateMoreButton() {
  moreMailsBtn.hidden = !nextPageToken || !gmailMessages.length;
}

function renderScanOverview() {
  const counts = gmailMessages.reduce((acc, message) => {
    const tag = String(message.risk_tag || "").toLowerCase();
    acc.total += 1;
    if (tag === "high") acc.high += 1;
    if (tag === "medium") acc.medium += 1;
    if (tag === "low") acc.low += 1;
    return acc;
  }, { total: 0, high: 0, medium: 0, low: 0 });

  mailCount.textContent = counts.total;
  highCount.textContent = counts.high;
  mediumCount.textContent = counts.medium;
  lowCount.textContent = counts.low;
}

function renderGmailResults(messages) {
  if (!messages.length) {
    gmailResults.className = "gmail-results empty";
    gmailResults.textContent = "No Gmail messages matched this query.";
    updateMoreButton();
    return;
  }

  gmailResults.className = "gmail-results";
  gmailResults.innerHTML = messages.map((message, index) => {
    const tag = String(message.risk_tag).toLowerCase();
    const id = message.gmail_id || message.subject || String(index);
    const sender = message.from || message.metadata?.from || "Unknown sender";
    const snippet = message.snippet || message.body || "";
    const accountSecurity = isAccountSecurityMail(message);
    const attachmentText = message.attachments?.length
      ? `${message.attachments.length} attachment(s)`
      : "No attachments";
    const linkText = message.links?.length ? `${message.links.length} link(s)` : "No links";
    return `
      <article class="gmail-item ${accountSecurity ? "account-security" : ""}" data-id="${escapeHtml(id)}">
        <button class="gmail-result" type="button" data-index="${index}">
          <span>
            <strong>${escapeHtml(message.subject || "(No subject)")}</strong>
            <small>From: ${escapeHtml(sender)}</small>
            <small>${accountSecurity ? "Account security | " : ""}${escapeHtml(attachmentText)} | ${escapeHtml(linkText)}</small>
            <small>${escapeHtml(snippet)}</small>
          </span>
          <b class="tag-${tag}">${escapeHtml(message.risk_tag)} ${message.risk_score}</b>
        </button>
      </article>
    `;
  }).join("");

  gmailResults.querySelectorAll(".gmail-result").forEach((button) => {
    button.addEventListener("click", () => {
      const message = messages[Number(button.dataset.index)];
      const id = message.gmail_id || message.subject || String(button.dataset.index);
      if (selectedGmailId === id) {
        collapseSelectedMail();
        return;
      }
      openSelectedMail(message);
    });
  });
  markSelectedMail();
}

function openSelectedMail(message) {
  selectedGmailId = message.gmail_id || message.subject || "";
  renderResult(message);
  renderMailReader(message);
  markSelectedMail();
}

function collapseSelectedMail() {
  selectedGmailId = "";
  mailReader.className = "mail-reader empty";
  mailReader.textContent = "Select a message to read its content.";
  markSelectedMail();
}

function markSelectedMail() {
  gmailResults.querySelectorAll(".gmail-result").forEach((button) => {
    const message = gmailMessages[Number(button.dataset.index)];
    const id = message?.gmail_id || message?.subject || "";
    button.classList.toggle("selected", Boolean(selectedGmailId && id === selectedGmailId));
  });
}

function renderMailReader(message) {
  const sender = message.from || message.metadata?.from || "Unknown sender";
  const date = message.date || "Unknown date";
  const body = message.body || message.snippet || "No readable plain-text content was found in this message.";
  const accountSecurity = isAccountSecurityMail(message);
  const linkCount = message.links?.length || 0;
  const attachmentCount = message.attachments?.length || 0;

  mailReader.className = `mail-reader ${accountSecurity ? "account-security-reader" : ""}`;
  mailReader.innerHTML = `
    <div class="reader-header">
      <div>
        <span class="section-title">Mail content</span>
        <h2>${escapeHtml(message.subject || "(No subject)")}</h2>
      </div>
      ${accountSecurity ? '<strong class="security-alert">Account security</strong>' : ""}
    </div>
    <div class="mail-meta">
      <div><span>Sender</span><strong>${escapeHtml(sender)}</strong></div>
      <div><span>Date</span><strong>${escapeHtml(date)}</strong></div>
    </div>
    <table class="mail-summary-table">
      <tbody>
        <tr><th>Risk</th><td>${escapeHtml(message.risk_tag)} (${message.risk_score})</td></tr>
        <tr><th>Links</th><td>${linkCount}</td></tr>
        <tr><th>Attachments</th><td>${attachmentCount}</td></tr>
        <tr><th>Words</th><td>${message.word_count || 0}</td></tr>
        <tr><th>Summary</th><td>${escapeHtml(message.summary || "No summary available.")}</td></tr>
      </tbody>
    </table>
    <div class="mail-block">
      <h2>Full mail content</h2>
      <pre>${escapeHtml(body)}</pre>
    </div>
  `;
}

function isAccountSecurityMail(message) {
  const text = `${message.subject || ""} ${message.body || ""} ${message.snippet || ""}`.toLowerCase();
  const patterns = [
    "account security",
    "security alert",
    "password",
    "verify your account",
    "account verification",
    "suspicious activity",
    "login attempt",
    "sign-in attempt",
    "2fa",
    "two-factor",
    "account recovery",
    "reset your password",
    "unusual activity",
    "access suspension",
  ];
  return patterns.some((pattern) => text.includes(pattern));
}

function renderResult(result) {
  const tag = result.risk_tag;
  const tagClass = tag.toLowerCase();

  riskBand.className = `risk-band ${tagClass}`;
  riskTag.textContent = `${tag} Risk`;
  riskTag.className = `risk-tag tag-${tagClass}`;
  riskScore.textContent = result.risk_score;
  guidance.textContent = result.guidance;
  summary.textContent = result.summary;
  wordCount.textContent = result.word_count;

  Object.entries(metricIds).forEach(([key, node]) => {
    node.textContent = result.category_scores[key] || 0;
  });

  if (!result.indicators.length) {
    indicatorList.className = "indicator-list empty";
    indicatorList.textContent = "No matched indicators";
    return;
  }

  indicatorList.className = "indicator-list";
  indicatorList.innerHTML = result.indicators.map((indicator) => `
    <article class="indicator">
      <div class="indicator-head">
        <div>
          <div class="indicator-title">${escapeHtml(indicator.label)}</div>
          <div class="phrases">${escapeHtml(indicator.description)}</div>
        </div>
        <span class="chip ${escapeHtml(indicator.category)}">+${indicator.weight}</span>
      </div>
      <div class="phrases">Matched: ${indicator.phrases.map(escapeHtml).join(", ")}</div>
    </article>
  `).join("");
}

function resetResults() {
  riskBand.className = "risk-band";
  riskTag.className = "risk-tag";
  riskTag.textContent = "Awaiting analysis";
  riskScore.textContent = "0";
  guidance.textContent = "Connect Gmail to scan real messages, or paste an email for manual testing.";
  summary.textContent = "No indicators have been evaluated yet.";
  indicatorList.className = "indicator-list empty";
  indicatorList.textContent = "No matched indicators";
  collapseSelectedMail();
  gmailMessages = [];
  nextPageToken = "";
  renderScanOverview();
  updateMoreButton();
  wordCount.textContent = "0";
  Object.values(metricIds).forEach((node) => {
    node.textContent = "0";
  });
}

async function loadGmailStatus() {
  try {
    const response = await fetch("/api/gmail/status");
    const status = await response.json();
    renderGmailStatus(status);
    if (status.connected) {
      await loadGmailProfile();
      await resetAndScan();
    }
  } catch (error) {
    gmailStatus.textContent = "Unable to check Gmail setup.";
  }
}

function renderGmailStatus(status, error = "") {
  if (!status) {
    gmailStatus.textContent = error || "Gmail setup status unavailable.";
    return;
  }

  const missing = [];
  if (!status.dependencies) missing.push("install Gmail API packages");
  if (!status.credentials_file) missing.push("add credentials.json");

  if (missing.length) {
    gmailStatus.textContent = `${error ? `${error} ` : ""}Setup needed: ${missing.join(", ")}.`;
  } else if (status.connected) {
    gmailStatus.textContent = "Connected with Gmail read-only access.";
  } else {
    gmailStatus.textContent = "Ready to connect. Sign in with Google to create token.json.";
  }
}

async function loadGmailProfile() {
  try {
    const response = await fetch("/api/gmail/profile");
    const data = await response.json();
    if (!data.ok) {
      accountEmail.textContent = "Profile unavailable";
      accountMeta.textContent = data.error || "Gmail read-only mode";
      return;
    }
    renderGmailProfile(data.profile);
  } catch (error) {
    accountEmail.textContent = "Profile unavailable";
    accountMeta.textContent = "Could not load Gmail account info";
  }
}

function renderGmailProfile(profile) {
  accountAvatar.textContent = profile.initial || "G";
  accountEmail.textContent = profile.email || "Connected Gmail";
  accountMeta.textContent = `${Number(profile.messages_total || 0).toLocaleString()} mails | ${Number(profile.threads_total || 0).toLocaleString()} threads`;
}

function setGmailBusy(isBusy, label = "") {
  connectGmailBtn.disabled = isBusy;
  scanGmailBtn.disabled = isBusy;
  connectAnotherBtn.disabled = isBusy;
  moreMailsBtn.disabled = isBusy;
  if (label) {
    scanGmailBtn.textContent = label;
  } else {
    scanGmailBtn.textContent = "Scan inbox";
  }
}

async function loadSamples() {
  const response = await fetch("/api/samples");
  const samples = await response.json();
  sampleList.innerHTML = samples.map((sample, index) => `
    <button class="sample-btn" type="button" data-index="${index}">
      ${escapeHtml(sample.name)}
    </button>
  `).join("");

  sampleList.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", async () => {
      const sample = samples[Number(button.dataset.index)];
      subjectInput.value = sample.subject;
      bodyInput.value = sample.body;
      await analyzeEmail();
    });
  });
}

async function loadHistory() {
  const response = await fetch("/api/history");
  const history = await response.json();

  if (!history.length) {
    historyList.className = "history-list empty";
    historyList.textContent = "No local history yet";
    return;
  }

  historyList.className = "history-list";
  historyList.innerHTML = history.slice().reverse().map((item) => {
    const tag = String(item.risk_tag).toLowerCase();
    return `
      <div class="history-item">
        <span class="history-subject">${escapeHtml(item.subject)}</span>
        <strong class="tag-${tag}">${escapeHtml(item.risk_tag)} ${item.risk_score}</strong>
      </div>
    `;
  }).join("");
}

function setBusy(isBusy) {
  const submit = form.querySelector("button[type='submit']");
  submit.disabled = isBusy;
  submit.textContent = isBusy ? "Analyzing..." : "Analyze risk";
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

loadSamples();
loadHistory();
loadGmailStatus();
