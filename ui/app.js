"Discord Personal Data Analyzer -- JS Frontend"

const EL = (id) => document.getElementById(id);
const BAR_COLORS = [
  "#89b4fa","#a6e3a1","#cba6f7","#fab387",
  "#94e2d5","#f9e2af","#f38ba8","#f5c2e7",
];

// ── State ──
let state = {
  data: null,
  voiceFilter: "all",
  dmSort: { key: "count", asc: false },
  serverSort: { key: "count", asc: false },
  sections: { dm: true, servers: true, voice: true, timeline: true },
  monthDrilldown: null,
  updateAvailable: false,
};

// ── API Bridge ──
function getPywebviewApi() {
  return new Promise((resolve, reject) => {
    if (window.pywebview?.api) {
      resolve(window.pywebview.api);
      return;
    }
    window.addEventListener("pywebviewready", () => {
      if (window.pywebview?.api) {
        resolve(window.pywebview.api);
      } else {
        reject(new Error("PyWebView bridge not available"));
      }
    }, { once: true });
  });
}

// ── Landing ──

function setupLanding() {
  const dropzone = EL("dropzone");
  const selectBtn = EL("selectBtn");

  dropzone.addEventListener("click", () => doSelectFile());
  dropzone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); doSelectFile(); }
  });

  // Drag-drop from OS uses the Python bridge
  selectBtn.addEventListener("click", () => doSelectFile());

  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropzone.classList.add("drag-over");
  });
  dropzone.addEventListener("dragleave", (e) => {
    e.preventDefault();
    dropzone.classList.remove("drag-over");
  });
  dropzone.addEventListener("drop", async (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropzone.classList.remove("drag-over");
    const dt = e.dataTransfer;
    let path = null;
    if (dt.files.length) {
      path = dt.files[0].path || dt.files[0].name;
    }
    if (!path && dt.getData("text")) {
      path = dt.getData("text").replace(/^file:\/\/\/?/, "");
    }
    if (path) {
      await analyzeFile(path);
    } else {
      EL("statusMsg").style.display = "block";
      EL("statusMsg").textContent = "Could not read file path. Use the button instead.";
    }
  });

  window.addEventListener("load", () => {
    if (window.location.protocol === "file:" && window.location.pathname.endsWith(".zip")) {
      analyzeFile(decodeURIComponent(window.location.pathname.replace(/^\//, "")));
    }
  });

  // Check for saved analysis + past analyses once the pywebview bridge is
  // actually ready (this used to run immediately at page load, before the
  // bridge existed, so it always silently failed).
  window.addEventListener("pywebviewready", async () => {
    let api;
    try {
      api = await getPywebviewApi();
    } catch (e) {
      console.warn("Bridge not available:", e);
      return;
    }

    try {
      const saved = await api.getSavedAnalysis();
      if (saved) {
        const btn = EL("continueBtn");
        btn.style.display = "block";
        btn.addEventListener("click", async () => {
          state.data = saved;
          EL("landing").style.display = "none";
          renderDashboard();
          try { await api.saveAnalysis(state.data); } catch (e) { console.warn("Failed to save analysis:", e); }
        });
      }
    } catch (e) { console.warn("Failed to check saved analysis:", e); }

    try {
      await setupMyAnalysesButton(api);
    } catch (e) { console.warn("Failed to set up My Analyses:", e); }
  }, { once: true });

  EL("importBtn").addEventListener("click", async () => {
    try {
      const api = await getPywebviewApi();
      const data = await api.importAnalysis();
      if (data) {
        state.data = data;
        EL("landing").style.display = "none";
        renderDashboard();
        try { await api.saveAnalysis(state.data); } catch (e) { console.warn("Failed to save imported analysis:", e); }
      } else {
        showToast("Invalid analysis file.");
      }
    } catch (e) {
      showToast("Import failed: " + (e.message || e));
    }
  });
}

// ── My Analyses Dropdown ──

async function setupMyAnalysesButton(api) {
  const btn = EL("myAnalysisBtn");
  const wrap = EL("myAnalysisWrap");
  if (!btn || !wrap) return;

  const analyses = await api.listSavedAnalyses();
  if (!analyses || !analyses.length) return;

  btn.style.display = "inline-flex";

  const dropdown = document.createElement("div");
  dropdown.className = "analysis-dropdown";
  dropdown.style.display = "none";
  dropdown.innerHTML = analyses.map((a) => {
    const msgs = nf(a.preview?.total_messages ?? 0);
    const voice = esc(a.preview?.total_voice_time ?? "0h 0m");
    return `<div class="analysis-dropdown-item" data-filename="${esc(a.filename)}">${esc(a.username)} — ${esc(a.date)} (${msgs} messages, ${voice} voice)</div>`;
  }).join("");
  wrap.appendChild(dropdown);

  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    dropdown.style.display = dropdown.style.display === "none" ? "block" : "none";
  });

  document.addEventListener("click", (e) => {
    if (!wrap.contains(e.target)) dropdown.style.display = "none";
  });

  dropdown.querySelectorAll(".analysis-dropdown-item").forEach((item) => {
    item.addEventListener("click", async () => {
      dropdown.style.display = "none";
      try {
        const data = await api.loadAnalysis(item.dataset.filename);
        if (data) {
          state.data = data;
          EL("landing").style.display = "none";
          renderDashboard();
        } else {
          showToast("Could not load that analysis.");
        }
      } catch (err) {
        showToast("Load failed: " + (err.message || err));
      }
    });
  });
}

async function doSelectFile() {
  EL("statusMsg").style.display = "block";
  EL("statusMsg").textContent = "Selecting file...";
  try {
    const api = await getPywebviewApi();
    const path = await api.selectFile();
    if (path) {
      await analyzeFile(path);
    } else {
      EL("statusMsg").textContent = "";
      EL("statusMsg").style.display = "none";
    }
  } catch (err) {
    EL("statusMsg").textContent = "Error: Bridge not available. Please restart the application.";
    EL("statusMsg").style.color = "#f38ba8";
  }
}

async function analyzeFile(path) {
  showLoading("Analyzing ZIP...");
  EL("landing").style.display = "none";
  try {
    const api = await getPywebviewApi();
    const data = await api.analyzeZip(path);
    if (!data) throw new Error("Analysis returned no data");
    state.data = data;
    hideLoading();
    renderDashboard();
    try { await api.saveAnalysis(state.data); } catch (e) { console.warn("Failed to persist analysis:", e); }
  } catch (err) {
    hideLoading();
    EL("landing").style.display = "flex";
    EL("statusMsg").textContent = "Error: " + (err.message || err);
    EL("statusMsg").style.color = "#f38ba8";
  }
}

// ── Loading ──
const PHASE_IDS = {
  "Extracting ZIP...": "phase-extract",
  "Analyzing messages...": "phase-messages",
  "Analyzing voice...": "phase-voice",
  "Building dashboard...": "phase-dashboard",
};

function updateProgress(phase) {
  const targetId = PHASE_IDS[phase];
  if (!targetId) return;
  let found = false;
  const items = document.querySelectorAll(".progress-item");
  for (const item of items) {
    if (item.id === targetId) {
      item.className = "progress-item active";
      found = true;
    } else if (!found) {
      item.className = "progress-item complete";
    } else {
      item.className = "progress-item";
    }
  }
}

function showLoading(text) {
  const ov = EL("loading");
  ov.classList.remove("hidden");
  const items = document.querySelectorAll(".progress-item");
  for (const item of items) {
    item.className = "progress-item";
  }
}

function hideLoading() {
  const items = document.querySelectorAll(".progress-item");
  for (const item of items) {
    item.className = "progress-item complete";
  }
  setTimeout(() => {
    EL("loading").classList.add("hidden");
  }, 300);
}

// ── Toast ──

function showToast(msg) {
  const el = EL("statusMsg");
  el.textContent = msg;
  el.style.display = "block";
  el.style.color = "var(--clr-dim)";
  setTimeout(() => { el.style.display = "none"; }, 2000);
}

function showUpdateBanner(version, url) {
  const banner = EL("updateBanner");
  EL("updateBannerText").innerHTML = "v" + version + " available — <a href=\"" + url + "\" target=\"_blank\">Download</a>";
  banner.style.display = "flex";
  state.updateAvailable = true;
  const icon = EL("checkUpdatesBtn");
  if (icon) icon.classList.add("has-update");
  EL("updateBannerDismiss").onclick = function() {
    banner.style.display = "none";
    // Icon stays green (has-update) — an update is still available even
    // though the banner itself was dismissed.
  };
}

// ── Dashboard ──

function renderDashboard() {
  const d = state.data;
  if (!d) return;
  EL("landing").style.display = "none";
  EL("dashboard").style.display = "flex";

  renderSummary(d);

  if (state.monthDrilldown) {
    EL("dmSection").style.display = "none";
    EL("serversSection").style.display = "none";
    EL("voiceSection").style.display = "none";
    renderTimeline(d);
    renderMonthDrilldown(state.monthDrilldown);
  } else {
    EL("dmSection").style.display = "";
    EL("serversSection").style.display = "";
    EL("voiceSection").style.display = "";
    EL("drilldownSection").style.display = "none";
    renderDMSection(d);
    renderServersSection(d);
    renderVoiceSection(d);
    renderTimeline(d);
  }

  EL("exportBtn").onclick = async () => {
    try {
      const api = await getPywebviewApi();
      const path = await api.exportAnalysis(state.data);
      if (path) showToast("Exported to " + path);
    } catch (e) {
      showToast("Export failed: " + (e.message || e));
    }
  };

  (function() {
    let lastCheck = 0;
    EL("checkUpdatesBtn").onclick = async () => {
      const now = Date.now();
      if (now - lastCheck < 2000) return;
      lastCheck = now;
      try {
        const api = await getPywebviewApi();
        await api.checkForUpdate();
        setTimeout(() => {
          if (!state.updateAvailable) {
            showToast("No update available.");
          }
        }, 1000);
      } catch (_) {
        showToast("Update check failed.");
      }
    };
  })();

  EL("newAnalysisBtn").onclick = () => {
    EL("dashboard").style.display = "none";
    EL("landing").style.display = "flex";
    EL("statusMsg").style.display = "none";
    state.data = null;
    state.monthDrilldown = null;
  };
}

// ── Summary Cards ──

function renderSummary(d) {
  const m = d.msg, v = d.voice;
  const cards = [
    { label: "Total Messages", value: nf(m.total_messages), color: "#89b4fa" },
    { label: "DM Messages",     value: nf(m.dm_total),       color: "#a6e3a1" },
    { label: "Server Messages", value: nf(m.server_total),   color: "#cba6f7" },
    { label: "Voice Time",      value: v.total_duration_formatted || "0h 0m", color: "#fab387" },
    { label: "Voice Sessions",  value: String(v.total_sessions || 0), color: "#94e2d5" },
  ];
  EL("summaryGrid").innerHTML = cards.map((c, i) => `
    <div class="card" style="border-left-color:${c.color};" tabindex="0">
      <div class="card-label">${c.label}</div>
      <div class="card-value" style="color:${c.color};">${c.value}</div>
    </div>
  `).join("");
}

// ── Section Factory ──

function sectionTemplate(id, title, subtitle, sortable, bodyHtml) {
  const isOpen = state.sections[id] !== false;
  const sortHtml = sortable ? `
    <div class="section-sort" tabindex="0" data-sort-section="${id}" title="Click to sort">
      <span class="section-sort-icon">${sortIndicator(id)}</span>
    </div>
  ` : "";
  return `
    <div class="section-header" tabindex="0" data-section-id="${id}">
      <span class="section-arrow${isOpen ? " open" : ""}">▶</span>
      <span class="section-title">${title}</span>
      ${subtitle ? `<span class="section-subtitle">${subtitle}</span>` : ""}
      ${sortHtml}
    </div>
    <div class="section-body${isOpen ? "" : " collapsed"}" ${isOpen ? 'style="max-height:2000px"' : ''}>
      <div class="section-body-inner chip-bar">${bodyHtml}</div>
    </div>
  `;
}

function sortIndicator(sectionId) {
  const sort = state[sectionId === "dm" ? "dmSort" : "serverSort"];
  if (sort.asc) return "▲";
  return "▼";
}

// ── DM Leaderboard ──

function renderDMSection(d) {
  const users = sortedDMUsers(d.dm_users);
  const total = d.dm_users.reduce((s, x) => s + x[1], 0);
  const max = users.length ? users[0][1] : 1;
  const body = users.slice(0, 12).map((u, i) => barRow(i + 1, u[0], u[1], max, i, "msgs")).join("");
  EL("dmSection").innerHTML = sectionTemplate("dm", "Top DM Contacts",
    `${d.dm_users.length} users, ${nf(total)} msgs`, true, body);
  bindSectionEvents("dm");
}

function renderServersSection(d) {
  const servers = d.servers.filter(s => !["Direct Messages", "Unknown"].includes(s[0]));
  servers.sort((a, b) => b[1] - a[1]);
  const total = servers.reduce((s, x) => s + x[1], 0);
  const max = servers.length ? servers[0][1] : 1;
  const body = servers.slice(0, 10).map((s, i) => barRow(0, s[0], s[1], max, i, "msgs")).join("");
  EL("serversSection").innerHTML = sectionTemplate("servers", "Servers",
    `${servers.length} servers, ${nf(total)} msgs`, true, body);
  bindSectionEvents("servers");
}

// ── Bar Row ──

function barRow(rank, name, value, max, idx, unit) {
  const w = max ? (value / max * 100) : 0;
  const color = BAR_COLORS[idx % BAR_COLORS.length];
  return `
    <div class="bar-row" tabindex="0" data-tooltip="${esc(name)}: ${nf(value)} ${unit}">
      ${rank ? `<span class="bar-rank">${rank}</span>` : ""}
      <span class="bar-name" style="width:${rank ? 140 : 160}px;">${esc(name)}</span>
      <div class="bar-track">
        <div class="bar-fill" style="width:${w}%;background:${color};"></div>
      </div>
    </div>
  `;
}

// ── Voice Section ──

function renderVoiceSection(d) {
  const v = d.voice;
  const ch = v.channel_durations || [];
  const totalSec = ch.reduce((s, c) => s + (c.duration_seconds || 0), 0);

  const filterChips = `
    <button class="chip${state.voiceFilter === "all" ? " active" : ""}" data-vf="all">All</button>
    <button class="chip${state.voiceFilter === "dm" ? " active" : ""}" data-vf="dm" style="--chip-color:#a6e3a1;">DM Calls</button>
    <button class="chip${state.voiceFilter === "server" ? " active" : ""}" data-vf="server" style="--chip-color:#cba6f7;">Server Channels</button>
  `;

  let body = filterChips;
  const dmEntries = ch.filter(c => c.name_type === "dm");
  const svEntries = ch.filter(c => c.name_type === "server");

  if (state.voiceFilter === "all" || state.voiceFilter === "dm") {
    if (dmEntries.length) {
      body += `<div style="font-weight:600;font-size:var(--fs-sm);color:#a6e3a1;margin-top:var(--sp-md);margin-bottom:var(--sp-sm);">DM Calls</div>`;
      const max = dmEntries[0]?.duration_seconds || 1;
      dmEntries.slice(0, 10).forEach((c, i) => {
        body += barRow(0, c.name.slice(0, 24), c.duration_seconds, max, i, formatHMS(c.duration_seconds) + ` (${c.call_count} calls)`);
      });
    }
  }
  if (state.voiceFilter === "all" || state.voiceFilter === "server") {
    if (svEntries.length) {
      const marginTop = (state.voiceFilter === "all" && dmEntries.length) ? "var(--sp-lg)" : "var(--sp-md)";
      body += `<div style="font-weight:600;font-size:var(--fs-sm);color:#cba6f7;margin-top:${marginTop};margin-bottom:var(--sp-sm);">Server Channels</div>`;
      svEntries.slice(0, 8).forEach(c => {
        body += `<div class="voice-row" tabindex="0">`
          + `<span class="bar-name">${esc(c.name.slice(0, 36))}</span>`
          + `<span style="font-size:var(--fs-sm);color:var(--color-dim);">${formatHMS(c.duration_seconds)} · ${c.call_count} sessions</span>`
          + `</div>`;
      });
    }
  }

  if (!dmEntries.length && !svEntries.length) {
    body += `<div class="empty-state">No voice data available</div>`;
  }

  EL("voiceSection").innerHTML = sectionTemplate("voice", "Voice Calls",
    formatHMS(totalSec) + " total", false, body);
  bindSectionEvents("voice");
  bindVoiceChips();
}

// ── Timeline ──

function renderTimeline(d) {
  const tl = d.timeline;
  const entries = Object.entries(tl).sort();
  const months = entries.slice(-24);
  const maxCount = Math.max(...months.map(e => e[1]), 1);

  const n = months.length;
  const LEFT_OFFSET = 44;  // px — aligns with .timeline-grid-line
  const RIGHT_OFFSET = 16; // px — aligns with .timeline-grid-line

  let gridLines = "", labels = "";
  gridLines += `<div class="timeline-grid-line" style="top:25%"></div>`;
  gridLines += `<div class="timeline-grid-line" style="top:50%"></div>`;
  gridLines += `<div class="timeline-grid-line" style="top:75%"></div>`;

  const bars = months.map((entry, i) => {
    const [period, count] = entry;
    const h = (count / maxCount * 100).toFixed(1);
    const color = BAR_COLORS[i % BAR_COLORS.length];
    const active = state.monthDrilldown === period ? " active" : "";
    return `<div class="timeline-bar${active}" style="height:${h}%;background:${color};" data-month="${period}" data-tip="${period}: ${nf(count)} messages" tabindex="0"></div>`;
  }).join("");

  months.forEach((entry, i) => {
    if (i % 3 === 0 || n <= 12) {
      const label = entry[0].length >= 7 ? entry[0].slice(2, 7) : entry[0];
      labels += `<div class="timeline-label" style="left:calc(${LEFT_OFFSET}px + ${(i + 0.5)} * (100% - ${LEFT_OFFSET + RIGHT_OFFSET}px) / ${n});">${label}</div>`;
    }
  });

  const body = `
    <div class="timeline-chart">
      ${gridLines}
      <div class="timeline-bars">${bars}</div>
      ${labels}
      <div class="timeline-max-label">${nf(maxCount)}</div>
    </div>
  `;

  EL("timelineSection").innerHTML = sectionTemplate("timeline", "Message Timeline",
    `${entries.length} months`, false, body);
  bindSectionEvents("timeline");
  bindTimelineEvents();
}

// ── Month Drill‑down ──

function renderMonthDrilldown(month) {
  const pm = state.data.per_month;
  const data = pm[month];
  const section = EL("drilldownSection");
  const title = EL("drilldownTitle");

  if (!data) {
    section.style.display = "none";
    state.monthDrilldown = null;
    return;
  }

  section.style.display = "";
  title.textContent = formatMonthLabel(month) + " — " + nf(data.total) + " messages";

  // ── Day chart: vertical bars for each day of the month ──
  const days = data.days || {};
  const dayEntries = Object.entries(days);
  const maxDay = dayEntries.length ? Math.max(...dayEntries.map(e => e[1])) : 1;
  const dn = dayEntries.length;

  let dayChartHtml = "";
  if (dayEntries.length) {
    const DAY_LEFT = 36;
    const DAY_RIGHT = 20;

    let dayGrid = `<div class="timeline-grid-line" style="top:25%"></div>`;
    dayGrid += `<div class="timeline-grid-line" style="top:50%"></div>`;
    dayGrid += `<div class="timeline-grid-line" style="top:75%"></div>`;

    const dayBars = dayEntries.map((entry, i) => {
      const [date, count] = entry;
      const h = (count / maxDay * 100).toFixed(1);
      const color = BAR_COLORS[i % BAR_COLORS.length];
      const dayNum = date.length >= 10 ? date.slice(8, 10) : date;
      const label = parseInt(dayNum, 10) + suffix(parseInt(dayNum, 10));
      return `<div class="timeline-bar" style="height:${h}%;background:${color};" data-tip="${label}: ${nf(count)} msgs"></div>`;
    }).join("");

    let dayLabels = "";
    dayEntries.forEach((entry, i) => {
      const step = dn <= 15 ? 2 : dn <= 25 ? 3 : 4;
      if (i % step === 0 || i === dn - 1) {
        const date = entry[0];
        const dayNum = date.length >= 10 ? parseInt(date.slice(8, 10), 10) : i + 1;
        dayLabels += `<div class="timeline-label" style="left:calc(${DAY_LEFT}px + ${(i + 0.5)} * (100% - ${DAY_LEFT + DAY_RIGHT}px) / ${dn});">${dayNum}</div>`;
      }
    });

    dayChartHtml = `
      <div class="section" style="margin-bottom:var(--sp-lg);">
        <div class="section-header" style="border-bottom:none;margin-bottom:0;padding-bottom:4px;cursor:default;">
          <span class="section-title">Daily Breakdown</span>
          <span class="section-subtitle">${dayEntries.length} days</span>
        </div>
        <div class="timeline-chart" style="margin-top:0;">
          ${dayGrid}
          <div class="timeline-bars">${dayBars}</div>
          ${dayLabels}
          <div class="timeline-max-label">${nf(maxDay)}</div>
        </div>
      </div>
    `;
  }

  EL("drilldownDayChart").innerHTML = dayChartHtml;
  bindDayChartHover();

  const dmUsers = data.dm_users || [];
  const servers = data.servers || [];
  const maxDM = dmUsers.length ? dmUsers[0][1] : 1;
  const maxSV = servers.length ? servers[0][1] : 1;

  let dmBody = dmUsers.slice(0, 12).map((u, i) =>
    barRow(i + 1, u[0], u[1], maxDM, i, "msgs")
  ).join("");
  if (!dmBody) dmBody = `<div class="empty-state">No DMs this month</div>`;

  let svBody = servers.slice(0, 10).map((s, i) =>
    barRow(0, s[0], s[1], maxSV, i, "msgs")
  ).join("");
  if (!svBody) svBody = `<div class="empty-state">No server messages this month</div>`;

  EL("drilldownDM").innerHTML = sectionTemplate("drilldown-dm", "DM Contacts",
    `${dmUsers.length} users`, false, dmBody);
  EL("drilldownServers").innerHTML = sectionTemplate("drilldown-sv", "Servers",
    `${servers.length} servers`, false, svBody);

  bindSectionEvents("drilldown-dm");
  bindSectionEvents("drilldown-sv");
}

function goBackToOverview() {
  state.monthDrilldown = null;
  renderDashboard();
}

function formatMonthLabel(ym) {
  const months = ["Jan","Feb","Mar","Apr","May","Jun",
                  "Jul","Aug","Sep","Oct","Nov","Dec"];
  const [y, m] = ym.split("-");
  return months[parseInt(m, 10) - 1] + " " + y;
}

// ── Event Binding ──

function bindSectionEvents(sectionId) {
  const el = sectionId === "dm" ? EL("dmSection")
    : sectionId === "servers" ? EL("serversSection")
    : sectionId === "voice" ? EL("voiceSection")
    : sectionId === "drilldown-dm" ? EL("drilldownDM")
    : sectionId === "drilldown-sv" ? EL("drilldownServers")
    : sectionId === "drilldown-days" ? EL("drilldownDayChart")
    : EL("timelineSection");

  // Collapse toggle
  const header = el.querySelector(".section-header");
  if (header) {
    header.addEventListener("click", () => toggleSection(sectionId));
    header.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        toggleSection(sectionId);
      }
    });
  }

  // Sort toggle
  const sortBtn = el.querySelector(".section-sort");
  if (sortBtn) {
    sortBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleSort(sectionId);
    });
    sortBtn.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault(); e.stopPropagation();
        toggleSort(sectionId);
      }
    });
  }

  // Tooltip on bar rows
  el.querySelectorAll("[data-tooltip]").forEach(row => {
    row.addEventListener("mouseenter", (e) => showTooltip(e, row.dataset.tooltip));
    row.addEventListener("mousemove", (e) => moveTooltip(e));
    row.addEventListener("mouseleave", hideTooltip);
  });
}

function bindVoiceChips() {
  EL("voiceSection").querySelectorAll(".chip[data-vf]").forEach(chip => {
    chip.addEventListener("click", () => {
      state.voiceFilter = chip.dataset.vf;
      renderVoiceSection(state.data);
    });
  });
}

function bindDayChartHover() {
  const section = EL("drilldownDayChart");
  if (!section) return;
  const bars = section.querySelectorAll(".timeline-bar");
  const tip = EL("tooltip");
  bars.forEach(bar => {
    bar.addEventListener("mouseenter", () => {
      tip.textContent = bar.dataset.tip;
      tip.classList.add("visible");
    });
    bar.addEventListener("mousemove", (e) => {
      tip.style.left = (e.clientX + 12) + "px";
      tip.style.top = (e.clientY - 28) + "px";
    });
    bar.addEventListener("mouseleave", () => {
      tip.classList.remove("visible");
    });
  });
}

function bindTimelineEvents() {
  const section = EL("timelineSection");
  const bars = section.querySelectorAll(".timeline-bar");
  const tip = EL("tooltip");

  bars.forEach(bar => {
    bar.addEventListener("mouseenter", () => {
      tip.textContent = bar.dataset.tip;
      tip.classList.add("visible");
    });
    bar.addEventListener("mousemove", (e) => {
      tip.style.left = (e.clientX + 12) + "px";
      tip.style.top = (e.clientY - 28) + "px";
    });
    bar.addEventListener("mouseleave", () => {
      tip.classList.remove("visible");
    });
    bar.addEventListener("click", () => {
      const month = bar.dataset.month;
      if (month) {
        state.monthDrilldown = state.monthDrilldown === month ? null : month;
        renderDashboard();
      }
    });
    bar.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        const month = bar.dataset.month;
        if (month) {
          state.monthDrilldown = state.monthDrilldown === month ? null : month;
          renderDashboard();
        }
      }
    });
  });

  const backBtn = EL("drilldownBackBtn");
  if (backBtn) {
    backBtn.onclick = goBackToOverview;
  }
}

function toggleSection(id) {
  state.sections[id] = state.sections[id] === false ? true : false;
  const el = id === "dm" ? EL("dmSection")
    : id === "servers" ? EL("serversSection")
    : id === "voice" ? EL("voiceSection")
    : id === "drilldown-dm" ? EL("drilldownDM")
    : id === "drilldown-sv" ? EL("drilldownServers")
    : id === "drilldown-days" ? EL("drilldownDayChart")
    : EL("timelineSection");

  const header = el.querySelector(".section-header");
  const body = el.querySelector(".section-body");
  const arrow = el.querySelector(".section-arrow");

  if (body) body.classList.toggle("collapsed");
  if (arrow) arrow.classList.toggle("open");
  if (header) header.setAttribute("aria-expanded", String(state.sections[id]));
}

function toggleSort(sectionId) {
  const key = sectionId === "dm" ? "dmSort" : "serverSort";
  const sort = state[key];
  if (!sort.asc) {
    state[key] = { key: sort.key, asc: true };
  } else {
    state[key] = { key: sort.key, asc: false };
  }
  if (sectionId === "dm") renderDMSection(state.data);
  else renderServersSection(state.data);
}

function sortedDMUsers(users) {
  const sort = state.dmSort;
  const arr = [...users];
  arr.sort((a, b) => sort.asc ? a[1] - b[1] : b[1] - a[1]);
  return arr;
}

// ── Tooltip ──

function showTooltip(e, text) {
  const tip = EL("tooltip");
  tip.textContent = text;
  tip.classList.add("visible");
  moveTooltip(e);
}

function moveTooltip(e) {
  const tip = EL("tooltip");
  tip.style.left = (e.clientX + 12) + "px";
  tip.style.top = (e.clientY - 28) + "px";
}

function hideTooltip() {
  EL("tooltip").classList.remove("visible");
}

// ── Helpers ──

function nf(n) { return n?.toLocaleString() ?? "0"; }
function esc(s) { return String(s).replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
function suffix(d) {
  if (d >= 11 && d <= 13) return "th";
  const last = d % 10;
  if (last === 1) return "st";
  if (last === 2) return "nd";
  if (last === 3) return "rd";
  return "th";
}
function formatHMS(sec) {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

// ── Init ──

setupLanding();

// Expose for pywebview bridge
window._onDropZip = async (path) => {
  EL("statusMsg").style.display = "block";
  EL("statusMsg").textContent = "Dropped: " + path;
  await analyzeFile(path);
};
