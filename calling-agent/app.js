const STORAGE_KEY = "callforge-simple-v3";
const EIGHTX8_URL = "https://work.8x8.com/calls/all";
let bridgeConnected = false;

const state = loadState();
const els = {
  csvInput: document.querySelector("#csvInput"),
  leadList: document.querySelector("#leadList"),
  leadCount: document.querySelector("#leadCount"),
  bridgeStatus: document.querySelector("#bridgeStatus"),
  leadName: document.querySelector("#leadName"),
  leadPhone: document.querySelector("#leadPhone"),
  callBtn: document.querySelector("#callBtn"),
  endBtn: document.querySelector("#endBtn"),
  liveScript: document.querySelector("#liveScript"),
  clearScriptBtn: document.querySelector("#clearScriptBtn"),
  notesInput: document.querySelector("#notesInput"),
  saveNextBtn: document.querySelector("#saveNextBtn"),
  prevBtn: document.querySelector("#prevBtn"),
  nextBtn: document.querySelector("#nextBtn"),
  exportBtn: document.querySelector("#exportBtn"),
};

function loadState() {
  const fallback = {
    leads: [],
    activeIndex: 0,
    script: "",
    selectedOutcome: "",
  };

  try {
    return { ...fallback, ...JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}") };
  } catch {
    return fallback;
  }
}

function persist() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

function activeLead() {
  return state.leads[state.activeIndex] || null;
}

function firstValue(row, keys) {
  for (const key of keys) {
    const normalized = row[normalizeKey(key)];
    const exact = row[key];
    const lower = row[key.toLowerCase()];
    const upper = row[key.toUpperCase()];
    const value = normalized ?? exact ?? lower ?? upper;
    if (value) return String(value).trim();
  }
  return "";
}

function normalizeLead(row, index) {
  const phone = firstValue(row, [
    "phone",
    "phone number",
    "phone_number",
    "mobile",
    "mobile number",
    "telephone",
    "tel",
    "number",
    "contact number",
    "business phone",
  ]);
  const business =
    firstValue(row, [
      "business",
      "business name",
      "company",
      "company name",
      "name",
      "organization",
      "organisation",
      "store",
      "place",
      "title",
      "lead name",
      "account name",
    ]) || inferBusinessName(row, phone);

  return {
    id: row.id || crypto.randomUUID(),
    business: business || `Lead ${index + 1}`,
    phone,
    notes: firstValue(row, ["notes", "Notes"]),
    outcome: firstValue(row, ["outcome", "Outcome"]),
    lastCalledAt: firstValue(row, ["last_called_at", "Last Called"]),
  };
}

function normalizeKey(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/^\uFEFF/, "")
    .replace(/[^a-z0-9]+/g, "");
}

function inferBusinessName(row, phone) {
  const cells = row.__cells || [];
  const phoneDigits = cleanPhone(phone);
  const candidate = cells.find((cell) => {
    const text = String(cell || "").trim();
    if (!text) return false;
    if (phoneDigits && cleanPhone(text) === phoneDigits) return false;
    if (/^[+\d\s().-]{7,}$/.test(text)) return false;
    if (/@/.test(text)) return false;
    if (/^https?:\/\//i.test(text)) return false;
    return /[a-zA-Z]/.test(text);
  });
  return candidate || "";
}

function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = "";
  let quoted = false;

  for (let i = 0; i < text.length; i += 1) {
    const char = text[i];
    const next = text[i + 1];

    if (char === '"' && quoted && next === '"') {
      field += '"';
      i += 1;
    } else if (char === '"') {
      quoted = !quoted;
    } else if (char === "," && !quoted) {
      row.push(field);
      field = "";
    } else if ((char === "\n" || char === "\r") && !quoted) {
      if (char === "\r" && next === "\n") i += 1;
      row.push(field);
      if (row.some((cell) => cell.trim())) rows.push(row);
      row = [];
      field = "";
    } else {
      field += char;
    }
  }

  row.push(field);
  if (row.some((cell) => cell.trim())) rows.push(row);
  if (rows.length < 2) return [];

  const headers = rows[0].map((cell) => cell.trim());
  return rows.slice(1).map((cells) => {
    const record = {};
    headers.forEach((header, index) => {
      const value = (cells[index] || "").trim();
      record[header] = value;
      record[header.toLowerCase()] = value;
      record[normalizeKey(header)] = value;
    });
    record.__cells = cells.map((cell) => String(cell || "").trim());
    return record;
  });
}

function cleanPhone(phone) {
  return String(phone || "").replace(/[^\d+]/g, "");
}

function render() {
  renderLeads();
  renderActiveLead();
  els.liveScript.value = state.script || "";
}

function renderLeads() {
  els.leadCount.textContent = `${state.leads.length} lead${state.leads.length === 1 ? "" : "s"}`;
  els.leadList.innerHTML = "";

  if (!state.leads.length) {
    const empty = document.createElement("div");
    empty.className = "lead-row";
    empty.innerHTML = "<strong>No leads yet</strong><span>Import a CSV to start calling.</span>";
    els.leadList.append(empty);
    return;
  }

  state.leads.forEach((lead, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `lead-row ${index === state.activeIndex ? "is-active" : ""} ${lead.outcome ? "done" : ""}`;
    button.innerHTML = `
      <strong>${escapeHtml(lead.business)}</strong>
      <small>${escapeHtml(lead.outcome || `${index + 1}/${state.leads.length}`)}</small>
      <span>${escapeHtml(lead.phone || "No phone")}</span>
    `;
    button.addEventListener("click", () => {
      saveCurrentLeadDraft();
      state.activeIndex = index;
      state.selectedOutcome = "";
      persist();
      render();
    });
    els.leadList.append(button);
  });
}

function renderActiveLead() {
  const lead = activeLead();
  const hasLead = Boolean(lead);
  const hasPhone = Boolean(cleanPhone(lead?.phone));

  els.leadName.textContent = lead?.business || "Import your leads";
  els.leadPhone.textContent = lead?.phone || "No number selected";
  els.notesInput.value = lead?.notes || "";
  els.callBtn.disabled = !hasLead || !hasPhone;
  els.endBtn.disabled = !hasLead;
  els.saveNextBtn.disabled = !hasLead;
  els.prevBtn.disabled = !hasLead || state.activeIndex <= 0;
  els.nextBtn.disabled = !hasLead || state.activeIndex >= state.leads.length - 1;

  document.querySelectorAll(".outcomes button").forEach((button) => {
    button.classList.toggle("is-selected", button.dataset.outcome === state.selectedOutcome || button.dataset.outcome === lead?.outcome);
  });
}

function saveCurrentLeadDraft() {
  const lead = activeLead();
  if (!lead) return;
  lead.notes = els.notesInput.value.trim();
}

function chooseOutcome(outcome) {
  state.selectedOutcome = outcome;
  renderActiveLead();
}

function saveAndNext() {
  const lead = activeLead();
  if (!lead) return;
  lead.notes = els.notesInput.value.trim();
  lead.outcome = state.selectedOutcome || lead.outcome || "Done";
  if (state.activeIndex < state.leads.length - 1) {
    state.activeIndex += 1;
    state.selectedOutcome = "";
  }
  persist();
  render();
}

function move(delta) {
  if (!state.leads.length) return;
  saveCurrentLeadDraft();
  state.activeIndex = Math.min(Math.max(state.activeIndex + delta, 0), state.leads.length - 1);
  state.selectedOutcome = "";
  persist();
  render();
}

async function sendBridgeCommand(action) {
  const lead = activeLead();
  if (!lead && action !== "end") return;
  const phone = cleanPhone(lead?.phone);

  const payload = {
    source: "callforge",
    action,
    phone,
    business: lead?.business || "",
  };

  window.postMessage(payload, window.location.origin);

  if (action === "dial") {
    els.callBtn.textContent = bridgeConnected ? "Sending..." : "Opening 8x8...";
    els.bridgeStatus.textContent = bridgeConnected
      ? "8x8 bridge: sending number to existing 8x8 tab"
      : "8x8 bridge: not connected, copied number and opened 8x8";
    await copyPhone(phone);

    if (!bridgeConnected) {
      window.open(EIGHTX8_URL, "callforge_8x8_tab");
    }
  } else {
    els.endBtn.textContent = "Ending...";
    els.bridgeStatus.textContent = bridgeConnected
      ? "8x8 bridge: trying to end call in existing 8x8 tab"
      : "8x8 bridge: not connected";
  }

  if (action === "dial" && lead) {
    lead.lastCalledAt = new Date().toISOString();
    persist();
  }

  window.setTimeout(() => {
    els.callBtn.textContent = "Call in 8x8";
    els.endBtn.textContent = "End call";
  }, 1200);
}

async function copyPhone(phone) {
  if (!phone) return;
  try {
    await navigator.clipboard.writeText(phone);
  } catch {
    const textarea = document.createElement("textarea");
    textarea.value = phone;
    document.body.append(textarea);
    textarea.select();
    document.execCommand("copy");
    textarea.remove();
  }
}

function exportLog() {
  saveCurrentLeadDraft();
  const headers = ["business", "phone", "outcome", "last_called_at", "notes"];
  const csv = [
    headers.join(","),
    ...state.leads.map((lead) => headers.map((header) => csvCell(lead[camelOrSame(header)] ?? lead[header] ?? "")).join(",")),
  ].join("\n");

  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `callforge-log-${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function camelOrSame(value) {
  return value.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
}

function csvCell(value) {
  const text = String(value ?? "");
  if (/[",\n\r]/.test(text)) return `"${text.replace(/"/g, '""')}"`;
  return text;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

els.csvInput.addEventListener("change", async (event) => {
  const file = event.target.files?.[0];
  if (!file) return;
  const rows = parseCsv(await file.text());
  state.leads = rows.map(normalizeLead).filter((lead) => lead.business || lead.phone);
  state.activeIndex = 0;
  state.selectedOutcome = "";
  persist();
  render();
});

els.liveScript.addEventListener("input", () => {
  state.script = els.liveScript.value;
  persist();
});

els.clearScriptBtn.addEventListener("click", () => {
  state.script = "";
  els.liveScript.value = "";
  persist();
});

document.querySelectorAll(".outcomes button").forEach((button) => {
  button.addEventListener("click", () => chooseOutcome(button.dataset.outcome));
});

els.callBtn.addEventListener("click", () => sendBridgeCommand("dial"));
els.endBtn.addEventListener("click", () => sendBridgeCommand("end"));
els.saveNextBtn.addEventListener("click", saveAndNext);
els.prevBtn.addEventListener("click", () => move(-1));
els.nextBtn.addEventListener("click", () => move(1));
els.exportBtn.addEventListener("click", exportLog);

window.addEventListener("message", (event) => {
  if (event.origin !== window.location.origin) return;
  const data = event.data || {};
  if (data.source !== "callforge-bridge") return;
  bridgeConnected = true;
  els.bridgeStatus.textContent = `8x8 bridge: ${data.status}`;
});

render();
