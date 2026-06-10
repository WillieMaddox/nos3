// NOS3-211 — NOS3 OnAIR detection-coverage overlay for the SPARTA demo app.
// Additive + self-contained: badges each technique card with real detection
// status and adds a per-sub-technique panel to the detail modal. Reads
// window.NOS3_COVERAGE / NOS3_COVERAGE_META (see gen_nos3_coverage.py).
// No edits to the app's render path — works via DOM enhancement + a wrapped
// openTechniqueModal, so it survives re-renders.
(function () {
  "use strict";
  const COV = window.NOS3_COVERAGE || {};
  const META = window.NOS3_COVERAGE_META || {};

  // All coverage entries for a card: the id itself + any "id.NN" sub-techniques.
  function entriesFor(id) {
    const out = [];
    if (COV[id]) out.push([id, COV[id]]);
    Object.keys(COV).forEach((k) => {
      if (k !== id && k.indexOf(id + ".") === 0) out.push([k, COV[k]]);
    });
    return out;
  }

  function statusOf(c) {
    if (c.tier === "OUT-OF-SCOPE") return { cls: "oos", label: "out of scope" };
    const det = c.incident_detected, n = c.incident_total;
    if (det != null && n) {
      if (det === n) return { cls: "det", label: "detected" };
      if (det > 0) return { cls: "part", label: "partial" };
      return { cls: "miss", label: "not detected" };
    }
    return { cls: "mon", label: "monitored" };
  }

  function aggregate(entries) {
    let mon = 0, det = 0, tot = 0, oos = 0;
    entries.forEach(([, c]) => {
      if (c.tier === "OUT-OF-SCOPE") { oos++; return; }
      mon++;
      if (c.incident_total) { tot += c.incident_total; det += (c.incident_detected || 0); }
    });
    return { mon, det, tot, oos, total: entries.length };
  }

  function badge(card) {
    if (card.dataset.nos3Done) return;
    const id = card.dataset.id;
    if (!id) return;
    const entries = entriesFor(id);
    if (!entries.length) return; // not a NOS3-evaluated technique
    card.dataset.nos3Done = "1";
    const a = aggregate(entries);
    let cls, text;
    if (a.mon === 0) {
      cls = "oos";
      text = "NOS3 · out of scope";
    } else {
      const recall = a.tot ? Math.round((100 * a.det) / a.tot) : null;
      cls = recall === null ? "mon" : recall >= 90 ? "det" : recall > 0 ? "part" : "miss";
      text = "NOS3 ▸ " + a.mon + " monitored" + (recall !== null ? " · " + recall + "% caught" : "");
    }
    const el = document.createElement("div");
    el.className = "nos3-badge " + cls;
    el.textContent = text;
    card.appendChild(el);
    card.classList.add("nos3-evaluated");
  }

  function badgeAll() {
    document.querySelectorAll(".technique-card[data-id]").forEach(badge);
  }

  function injectModalPanel(techId) {
    const host = document.getElementById("techniqueDescription");
    if (!host) return;
    const old = document.getElementById("nos3-panel");
    if (old) old.remove();
    const entries = entriesFor(techId);
    if (!entries.length) return;
    const rows = entries.map(([id, c]) => {
      const st = statusOf(c);
      const rec = c.incident_total ? c.incident_detected + "/" + c.incident_total : "—";
      const lab = (c.label_ok != null && c.incident_detected) ? " (" + c.label_ok + " labeled ✓)" : "";
      return (
        "<tr><td class='nid'>" + id + "</td><td>" + (c.name || "") +
        "</td><td><span class='nos3-pill " + st.cls + "'>" + st.label + "</span></td>" +
        "<td>" + c.tier + "</td><td>" + c.signal + "</td>" +
        "<td>" + (c.frame_rate != null ? Math.round(c.frame_rate * 100) + "%" : "—") + "</td>" +
        "<td>" + rec + lab + "</td></tr>"
      );
    }).join("");
    const div = document.createElement("div");
    div.id = "nos3-panel";
    div.className = "nos3-panel";
    div.innerHTML =
      "<div class='nos3-panel-h'>🛰️ NOS3 OnAIR Detection Coverage" +
      "<span class='nos3-sub'>" + (META.model || "") + "</span></div>" +
      "<table class='nos3-table'><thead><tr>" +
      "<th>Sub-technique</th><th>Name</th><th>Status</th><th>Classifier tier</th>" +
      "<th>Signal class</th><th title='frame-level SUNSAFE catch rate'>Frame catch</th>" +
      "<th title='incident-level recall across corpus instances'>Incident</th>" +
      "</tr></thead><tbody>" + rows + "</tbody></table>" +
      "<div class='nos3-foot'>Status = incident-level detection on the labeled corpus " +
      "(an attack counts as caught if it raised ≥1 alert). \"Frame catch\" is the per-frame " +
      "SUNSAFE flag rate. Signal class = telemetry observability: ON_BOARD (visible) · " +
      "OBFUSCATION (self-hidden) · UNSUBSCRIBED (not monitored) · CONCEPTUAL (no-op).</div>";
    host.parentNode.insertBefore(div, host.nextSibling);
  }

  function addLegend() {
    if (document.getElementById("nos3-legend")) return;
    const rh = META.incident_recall_headline != null
      ? Math.round(META.incident_recall_headline * 100) + "%" : "";
    const L = document.createElement("div");
    L.id = "nos3-legend";
    L.className = "nos3-legend";
    L.innerHTML =
      "<button class='nos3-x' title='hide' onclick=\"this.parentNode.style.display='none'\">×</button>" +
      "<strong>🛰️ NOS3 detection overlay</strong> " +
      "<span class='nos3-pill det'>detected</span>" +
      "<span class='nos3-pill part'>partial</span>" +
      "<span class='nos3-pill miss'>not detected</span>" +
      "<span class='nos3-pill mon'>monitored</span>" +
      "<span class='nos3-pill oos'>out of scope</span>" +
      (rh ? "<span class='nos3-rh'>corpus incident recall " + rh + "</span>" : "");
    document.body.appendChild(L);
  }

  const CSS =
    ".nos3-badge{margin-top:.45rem;font-family:var(--font-mono,monospace);font-size:.62rem;" +
    "font-weight:600;letter-spacing:.02em;padding:.15rem .4rem;border-radius:4px;display:inline-block;" +
    "border:1px solid transparent}" +
    ".technique-card.nos3-evaluated{position:relative}" +
    ".nos3-badge.det{background:rgba(34,197,94,.16);color:#16a34a;border-color:rgba(34,197,94,.4)}" +
    ".nos3-badge.part{background:rgba(245,158,11,.16);color:#d97706;border-color:rgba(245,158,11,.4)}" +
    ".nos3-badge.miss{background:rgba(239,68,68,.15);color:#dc2626;border-color:rgba(239,68,68,.4)}" +
    ".nos3-badge.mon{background:rgba(59,130,246,.15);color:#2563eb;border-color:rgba(59,130,246,.4)}" +
    ".nos3-badge.oos{background:rgba(148,163,184,.15);color:#64748b;border-color:rgba(148,163,184,.4)}" +
    ".nos3-pill{font-family:var(--font-mono,monospace);font-size:.64rem;font-weight:600;padding:.1rem .4rem;" +
    "border-radius:10px;margin-left:.25rem;white-space:nowrap}" +
    ".nos3-pill.det{background:rgba(34,197,94,.16);color:#16a34a}" +
    ".nos3-pill.part{background:rgba(245,158,11,.16);color:#d97706}" +
    ".nos3-pill.miss{background:rgba(239,68,68,.15);color:#dc2626}" +
    ".nos3-pill.mon{background:rgba(59,130,246,.15);color:#2563eb}" +
    ".nos3-pill.oos{background:rgba(148,163,184,.18);color:#64748b}" +
    ".nos3-panel{margin:1rem 0;border:1px solid var(--border-color,#2a3344);border-radius:8px;" +
    "background:var(--bg-secondary,#11161f);overflow:hidden}" +
    ".nos3-panel-h{padding:.6rem .8rem;font-weight:700;background:rgba(59,130,246,.1);" +
    "border-bottom:1px solid var(--border-color,#2a3344);display:flex;justify-content:space-between;align-items:center}" +
    ".nos3-sub{font-family:var(--font-mono,monospace);font-size:.62rem;font-weight:500;opacity:.7}" +
    ".nos3-table{width:100%;border-collapse:collapse;font-size:.72rem}" +
    ".nos3-table th,.nos3-table td{padding:.35rem .55rem;text-align:left;border-bottom:1px solid var(--border-color,#222b38)}" +
    ".nos3-table th{font-size:.6rem;text-transform:uppercase;letter-spacing:.04em;opacity:.65}" +
    ".nos3-table td.nid,.nos3-table .nid{font-family:var(--font-mono,monospace);font-weight:600}" +
    ".nos3-foot{padding:.5rem .8rem;font-size:.64rem;opacity:.7;line-height:1.4}" +
    ".nos3-legend{position:fixed;left:14px;bottom:14px;z-index:9999;background:var(--bg-secondary,#11161f);" +
    "border:1px solid var(--border-color,#2a3344);border-radius:10px;padding:.5rem .7rem;" +
    "box-shadow:0 6px 24px rgba(0,0,0,.4);font-size:.66rem;display:flex;gap:.3rem;align-items:center;flex-wrap:wrap;max-width:min(92vw,640px)}" +
    ".nos3-legend strong{font-size:.7rem;margin-right:.2rem}" +
    ".nos3-rh{margin-left:.4rem;font-family:var(--font-mono,monospace);font-weight:600;opacity:.85}" +
    ".nos3-x{position:absolute;top:-9px;right:-9px;width:20px;height:20px;border-radius:50%;border:none;" +
    "background:#334155;color:#fff;cursor:pointer;font-size:.8rem;line-height:1}";

  function start() {
    try {
      const s = document.createElement("style");
      s.textContent = CSS;
      document.head.appendChild(s);
      addLegend();
      badgeAll();
      const grid = document.getElementById("matrixGrid");
      if (grid && window.MutationObserver) {
        new MutationObserver(function () { badgeAll(); })
          .observe(grid, { childList: true, subtree: true });
      }
      if (typeof window.openTechniqueModal === "function") {
        const orig = window.openTechniqueModal;
        window.openTechniqueModal = function (id) {
          const r = orig.apply(this, arguments);
          try { injectModalPanel(id); } catch (e) { console.warn("[nos3] panel", e); }
          return r;
        };
      }
      console.log("[nos3] coverage overlay active:", Object.keys(COV).length, "techniques");
    } catch (e) {
      console.warn("[nos3] overlay init failed", e);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
