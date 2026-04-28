const els = {
  viewMode: document.getElementById("viewMode"),
  dailySelect: document.getElementById("dailySelect"),
  weeklySelect: document.getElementById("weeklySelect"),
  dailyWrap: document.getElementById("dailyWrap"),
  weeklyWrap: document.getElementById("weeklyWrap"),
  kpis: document.getElementById("kpis"),
  summary: document.getElementById("summary"),
  topIssues: document.getElementById("topIssues"),
  barcodeTable: document.getElementById("barcodeTable"),
  spokeTable: document.getElementById("spokeTable"),
  hubTable: document.getElementById("hubTable"),
};

const STATUS_KEYS = [
  "returns",
  "delayedArrival",
  "lateSort",
  "noSpokeScan",
  "incorrectFacility",
  "parcelPlannerMiss",
  "deliveredLate",
  "sortAppRollover",
  "lostAtHubTransport",
  "lostAtSpoke",
  "otdBy8pm",
  "autoReschedule",
  "siteRollover",
  "others",
];

const STATUS_LABELS = {
  returns: "Returns",
  delayedArrival: "Delayed Arrival",
  lateSort: "Late Sort",
  noSpokeScan: "No Spoke Scan",
  incorrectFacility: "Incorrect Facility",
  parcelPlannerMiss: "Planner Miss",
  deliveredLate: "Delivered Late",
  sortAppRollover: "Sort Rollover",
  lostAtHubTransport: "Lost Hub/Trans",
  lostAtSpoke: "Lost at Spoke",
  otdBy8pm: "OTD by 8pm",
  autoReschedule: "Auto Resched",
  siteRollover: "Site Rollover",
  others: "Others",
};

function sum(arr, key) {
  return arr.reduce((acc, item) => acc + (item[key] || 0), 0);
}

function avg(arr, key) {
  return arr.length ? sum(arr, key) / arr.length : 0;
}

function fmtPct(v) {
  return `${v.toFixed(1)}%`;
}

function issueTotal(spoke) {
  return STATUS_KEYS.reduce((acc, k) => acc + (spoke[k] || 0), 0);
}

/** Raw Excel export uses "1.otd"; show a cleaner label in the UI. */
function formatBarcodeStatusLabel(status) {
  if (typeof status !== "string") return status;
  if (status.trim().toLowerCase() === "1.otd") return "otd";
  return status;
}

/** First letter of each word uppercase (rest lowercase) for barcode breakdown display. */
function capitalizeWord(word) {
  const i = word.search(/[a-zA-Z]/);
  if (i === -1) return word;
  return word.slice(0, i) + word.charAt(i).toUpperCase() + word.slice(i + 1).toLowerCase();
}

function formatBarcodeStatusForDisplay(status) {
  let s = formatBarcodeStatusLabel(status);
  if (typeof s !== "string") return s;
  const t = s.trim();
  if (t.toLowerCase() === "otd") return "OTD";
  return t.split(/\s+/).map(capitalizeWord).join(" ");
}

function getCurrentPeriod() {
  const mode = els.viewMode.value;
  if (mode === "daily") {
    return window.DASHBOARD_DATA.dailySnapshots[els.dailySelect.value];
  }
  return window.DASHBOARD_DATA.weeklySnapshots[els.weeklySelect.value];
}

function renderKPIs(period) {
  const spokes = period.spokes;
  const hubs = period.hubs;
  const html = [
    ["Active Spokes", spokes.length],
    ["Avg Spoke OTD", fmtPct(avg(spokes, "otd"))],
    ["Total Returns", sum(spokes, "returns")],
    ["Total Delayed", sum(spokes, "delayedArrival") + sum(spokes, "lateSort")],
    ["Avg Hub CPT", fmtPct(avg(hubs, "onTimeCpt"))],
  ]
    .map(([l, v]) => `<div class="kpi"><div class="v">${v}</div><div class="l">${l}</div></div>`)
    .join("");
  els.kpis.innerHTML = html;
}

function renderTopIssues(period) {
  const top = [...period.spokes].sort((a, b) => issueTotal(b) - issueTotal(a)).slice(0, 12);
  const max = top.length ? issueTotal(top[0]) : 1;
  els.topIssues.innerHTML = top
    .map((s) => {
      const val = issueTotal(s);
      const w = Math.max(2, (val / max) * 100);
      return `<div class="bar-row"><div class="bar-label"><span>${s.code}</span><span>${val}</span></div><div class="bar"><span style="width:${w}%"></span></div></div>`;
    })
    .join("");
}

function renderBarcodeTable(period) {
  const rows = period.barcode || [];
  const total = rows.reduce((a, b) => a + b.count, 0);
  const head = `<tr><th>Barcode Status</th><th>Count</th><th>Share</th></tr>`;
  const body = rows
    .map(
      (r) =>
        `<tr><td>${formatBarcodeStatusForDisplay(r.status)}</td><td>${r.count}</td><td>${total ? fmtPct((r.count / total) * 100) : "0.0%"}</td></tr>`
    )
    .join("");
  els.barcodeTable.innerHTML = head + body;
}

function renderSpokeTable(period) {
  const spokes = [...period.spokes].sort((a, b) => a.otd - b.otd);
  const headers = ["Spoke", "OTD", ...STATUS_KEYS.map((k) => STATUS_LABELS[k])];
  const head = `<tr>${headers.map((h) => `<th>${h}</th>`).join("")}</tr>`;
  const body = spokes
    .map((s) => {
      const tds = [`<td>${s.code}</td>`, `<td>${fmtPct(s.otd)}</td>`, ...STATUS_KEYS.map((k) => `<td>${s[k] || 0}</td>`)];
      return `<tr>${tds.join("")}</tr>`;
    })
    .join("");
  els.spokeTable.innerHTML = head + body;
}

function renderHubTable(period) {
  const head = `<tr><th>Hub</th><th>On-Time CPT</th><th>Missorts</th><th>Missort Rate</th></tr>`;
  const body = (period.hubs || [])
    .map((h) => `<tr><td>${h.code}</td><td>${fmtPct(h.onTimeCpt || 0)}</td><td>${h.missorts || 0}</td><td>${fmtPct(h.missortRate || 0)}</td></tr>`)
    .join("");
  els.hubTable.innerHTML = head + body;
}

function render() {
  els.dailyWrap.style.display = els.viewMode.value === "daily" ? "flex" : "none";
  els.weeklyWrap.style.display = els.viewMode.value === "weekly" ? "flex" : "none";
  const period = getCurrentPeriod();
  renderKPIs(period);
  renderSummary(period);
  renderTopIssues(period);
  renderBarcodeTable(period);
  renderSpokeTable(period);
  renderHubTable(period);
}

function init() {
  const dailyKeys = Object.keys(window.DASHBOARD_DATA.dailySnapshots);
  const weeklyKeys = Object.keys(window.DASHBOARD_DATA.weeklySnapshots);
  els.dailySelect.innerHTML = dailyKeys.map((k) => `<option value="${k}">${k}</option>`).join("");
  els.weeklySelect.innerHTML = weeklyKeys.map((k) => `<option value="${k}">${k}</option>`).join("");
  els.dailySelect.value = dailyKeys[dailyKeys.length - 1];
  els.weeklySelect.value = weeklyKeys[0];
  els.viewMode.addEventListener("change", render);
  els.dailySelect.addEventListener("change", render);
  els.weeklySelect.addEventListener("change", render);
  render();
}

init();

// ── Summary ──────────────────────────────────────────────────────────────────

const OTD_RED        = 80;
const OTD_YELLOW     = 92;
const CPT_RED        = 80;
const CPT_YELLOW     = 92;
const MISSORT_RED    = 2.0;
const MISSORT_YELLOW = 1.0;

function badge(color, text) {
  return `<span class="badge badge-${color}">${text}</span>`;
}

function spokeBadge(otd) {
  if (otd < OTD_RED)    return badge("red",    "Critical");
  if (otd < OTD_YELLOW) return badge("yellow", "At Risk");
  return badge("green", "On Track");
}

function hubCptBadge(cpt) {
  if (cpt < CPT_RED)    return badge("red",    "Critical");
  if (cpt < CPT_YELLOW) return badge("yellow", "At Risk");
  return badge("green", "On Track");
}

function hubMissortBadge(rate) {
  if (rate >= MISSORT_RED)    return badge("red",    "High");
  if (rate >= MISSORT_YELLOW) return badge("yellow", "Elevated");
  return badge("green", "Normal");
}

function topNArr(arr, key, n, descending) {
  return [...arr].sort((a, b) => descending ? b[key] - a[key] : a[key] - b[key]).slice(0, n);
}

function renderSummary(period) {
  if (!els.summary) return;
  const spokes   = period.spokes || [];
  const hubs     = period.hubs   || [];
  const isWeekly = els.viewMode.value === "weekly";
  const bullets  = [];

  // Worst OTD spokes
  const worstSpokes = topNArr(spokes, "otd", 3, false);
  if (worstSpokes.length) {
    bullets.push(`<li class="summary-group-header">🔴 Bottom Spokes by OTD</li>`);
    worstSpokes.forEach(s => {
      bullets.push(`<li>${spokeBadge(s.otd)} <strong>${s.code}</strong> — OTD ${fmtPct(s.otd)}</li>`);
    });
  }

  // Top issue categories
  const issueTotals = STATUS_KEYS.map(k => ({
    key: k, label: STATUS_LABELS[k],
    total: spokes.reduce((acc, s) => acc + (s[k] || 0), 0),
  })).filter(i => i.total > 0).sort((a, b) => b.total - a.total).slice(0, 5);

  if (issueTotals.length) {
    bullets.push(`<li class="summary-group-header">📦 Top Issue Categories${isWeekly ? " (Week Total)" : ""}</li>`);
    issueTotals.forEach((i, idx) => {
      const color = idx === 0 ? "red" : idx === 1 ? "yellow" : "neutral";
      bullets.push(`<li>${badge(color, "#" + (idx + 1))} <strong>${i.label}</strong> — ${i.total.toLocaleString()} parcels</li>`);
    });
  }

  // Hub CPT callouts
  const badCptHubs = hubs.filter(h => h.onTimeCpt < OTD_YELLOW).sort((a, b) => a.onTimeCpt - b.onTimeCpt);
  bullets.push(`<li class="summary-group-header">🏭 Hub On-Time CPT</li>`);
  if (badCptHubs.length) {
    badCptHubs.forEach(h => {
      bullets.push(`<li>${hubCptBadge(h.onTimeCpt)} <strong>${h.code}</strong> — CPT ${fmtPct(h.onTimeCpt)}</li>`);
    });
  } else {
    bullets.push(`<li>${badge("green", "All Clear")} All hubs above ${OTD_YELLOW}% on-time CPT</li>`);
  }

  // Hub missort callouts
  const badMissortHubs = hubs.filter(h => h.missortRate >= MISSORT_YELLOW).sort((a, b) => b.missortRate - a.missortRate);
  bullets.push(`<li class="summary-group-header">⚠️ Hub Missort Rates</li>`);
  if (badMissortHubs.length) {
    badMissortHubs.forEach(h => {
      bullets.push(`<li>${hubMissortBadge(h.missortRate)} <strong>${h.code}</strong> — ${fmtPct(h.missortRate)} missort rate (${h.missorts} missorts)</li>`);
    });
  } else {
    bullets.push(`<li>${badge("green", "All Clear")} All hubs below ${MISSORT_YELLOW}% missort rate</li>`);
  }

  // Overall health
  const avgOtd       = avg(spokes, "otd");
  const criticalCount = spokes.filter(s => s.otd < OTD_RED).length;
  const atRiskCount   = spokes.filter(s => s.otd >= OTD_RED && s.otd < OTD_YELLOW).length;
  const onTrackCount  = spokes.length - criticalCount - atRiskCount;
  const overallColor  = criticalCount > 0 ? "red" : atRiskCount > 2 ? "yellow" : "green";
  const overallLabel  = criticalCount > 0 ? "Needs Attention" : atRiskCount > 2 ? "Mixed" : "Healthy";

  els.summary.innerHTML = `
    <div class="summary-header">
      <span class="summary-title">${isWeekly ? "Weekly" : "Daily"} Performance Summary</span>
      <span class="summary-chips">
        ${badge(overallColor, overallLabel)}
        <span class="summary-stat">Avg OTD ${fmtPct(avgOtd)}</span>
        <span class="summary-stat">${badge("red","Critical")} ${criticalCount}</span>
        <span class="summary-stat">${badge("yellow","At Risk")} ${atRiskCount}</span>
        <span class="summary-stat">${badge("green","On Track")} ${onTrackCount}</span>
      </span>
    </div>
    <ul class="summary-list">${bullets.join("")}</ul>`;
}
