// NOS3-211 — NOS3/OnAIR detection-coverage overlay for the SPARTA coverage page.
// Additive + self-contained: badges each technique card with a per-sub-technique
// rollup (segmented bar, one block per sub coloured by its own verdict) and adds a
// per-sub-technique panel to the detail modal. Reads window.NOS3_COVERAGE /
// NOS3_COVERAGE_META (see gen_nos3_coverage.py) and the base app's spartaData /
// findTechnique for the full sub-technique list.
// No edits to the app's render path — works via DOM enhancement + a wrapped
// openTechniqueModal, so it survives re-renders.
(function () {
  "use strict";
  const COV = window.NOS3_COVERAGE || {};
  const META = window.NOS3_COVERAGE_META || {};

  // ── Verdict vocabulary ─────────────────────────────────────────────────────
  // det  detected      — evaluated, caught (classifier >=90% or a gate incident)
  // part partial        — evaluated, caught some of the time / some sub-techniques
  // miss not detected  — evaluated, missed
  // mon  monitored      — in scope + telemetry subscribed, catch-rate not yet scored
  // oos  out of scope   — applies to NOS3 but no telemetry signal possible (Section C)
  // na   not applicable — the attack can't run against NOS3 at all (Section D)
  // none not evaluated  — a real sub-technique NOS3 hasn't assessed yet (blank pill)
  const LABEL = {
    det: "detected", part: "partial", miss: "not detected", mon: "monitored",
    oos: "out of scope", na: "not applicable", none: "not evaluated",
  };
  const ORDER = ["det", "part", "miss", "none", "oos", "na"]; // "mon" dropped — no technique resolves to it

  // Whole-tactic Not-Applicable (off-board / not modelled). Prefix -> reason.
  // Mirrors SPARTA_COVERAGE_TRIAGE.md Section D.
  const NA_TACTIC = {
    REC: "Reconnaissance is off-board information-gathering about the target — nothing executes on the spacecraft, so there is no on-board attack surface to observe.",
    RD: "Resource development is the attacker building infrastructure or malware off-board; it never touches the spacecraft.",
    IA: "Initial access is the entry vector (ground / supply-chain / RF). Its on-board result — a malicious command or code — is a separate Execution technique, which is where NOS3 detects.",
    LM: "Lateral movement needs a hosted payload, crosslink, VM, or proximity target; NOS3 is a single satellite modelling none of these. (Exception: LM-0002 bus segregation.)",
    EXF: "Exfiltration relies on physical side-channels, RF, or off-board sites NOS3 doesn't model. (Exception: EXF-0003.02 downlink exfil.)",
  };
  // N/A techniques inside otherwise-applicable tactics (target not modelled).
  // id or id-prefix -> reason.
  const NA_TECH = {
    "EX-0004": "Boot-ROM / boot-memory tampering targets a boot layer NOS3 doesn't model — there is no such target in the simulation.",
    "EX-0005.01": "Design-flaw exploitation targets device firmware / FPGA logic / hardware registers. NOS3 models subsystems at the functional level only — there is no firmware layer to corrupt (AINOS3-75). Its effect-equivalent (corrupted sensor output) is covered by EX-0012 / EX-0014.",
    "EX-0007": "Single-event upset is a radiation / hardware fault; NOS3 models no SEU mechanism to attack.",
    "EX-0012.06": "Targets a science / payload subsystem NOS3 doesn't carry.",
    "EX-0014.05": "Missile-warning spoof targets a sensor / payload absent from the NOS3 model.",
    "EX-0015": "Side-channel attack is a physical-layer effect with no software-bus representation.",
    "EX-0016": "RF jamming is a physical-layer effect with no cFS software-bus representation.",
    "EX-0017": "Anti-satellite / kinetic attack is a physical-domain event, not a software one NOS3 can model.",
    "EX-0018": "Directed-energy attack is a physical / RF effect NOS3 doesn't model.",
    "DE-0002.01": "Ground-segment evasion happens off-board; NOS3 models no ground system.",
    "DE-0002.02": "RF jamming for evasion is a physical-layer effect with no software-bus footprint.",
    "DE-0009": "Space-domain-awareness evasion targets external tracking, not the on-board FSW.",
    "PER-0003": "Ground-segment persistence lives off-board; NOS3 models no ground system.",
    "EXF-0002": "Physical side-channel exfiltration; no software-bus representation.",
  };
  // Applicable exceptions that must NOT be swept into their tactic's N/A verdict —
  // they fall through to "not evaluated" instead. (LM-0002 is in COV anyway.)
  const NA_EXCEPT = ["LM-0002", "EXF-0003.02"];

  function tacticOf(id) { return id.split("-")[0]; }
  function pref(id, key) { return id === key || id.indexOf(key + ".") === 0; }

  // Reason a technique/sub-technique is Not-Applicable, else null.
  function naReason(id) {
    for (const k in NA_TECH) { if (pref(id, k)) return NA_TECH[k]; }
    for (const e of NA_EXCEPT) { if (pref(id, e)) return null; }
    const r = NA_TACTIC[tacticOf(id)];
    return r || null;
  }

  // Verdict class for a COVERAGE entry (evaluated by NOS3).
  function covStatus(c) {
    if (c.tier === "OUT-OF-SCOPE") return "oos";
    if (c.gate) return "det"; // gate-detected: live incident even though the IF misses it
    const det = c.incident_detected, n = c.incident_total;
    if (det != null && n) return det === n ? "det" : det > 0 ? "part" : "miss";
    return "mon";
  }

  // Base-app name for a technique/sub id (for na / not-evaluated rows).
  function nameFromData(id) {
    if (typeof findTechnique !== "function") return "";
    if (id.indexOf(".") > 0) {
      const parent = id.slice(0, id.indexOf("."));
      const r = findTechnique(parent);
      const sub = r && r.technique.subtechniques && r.technique.subtechniques[id];
      return (sub && sub.name) || "";
    }
    const r = findTechnique(id);
    return (r && r.technique.name) || "";
  }

  // Unified verdict for ANY technique/sub id: coverage entry, N/A, or not-evaluated.
  function statusForId(id) {
    if (COV[id]) return { cls: covStatus(COV[id]), c: COV[id] };
    const na = naReason(id);
    if (na) {
      return { cls: "na", c: { name: nameFromData(id), tier: "NOT-APPLICABLE", signal: "—", review: na } };
    }
    return { cls: "none", c: { name: nameFromData(id), tier: "—", signal: "—", review: "" } };
  }

  // The leaf rows for a technique card, from the base SPARTA data: its
  // sub-techniques if any, else the technique itself. Prepends the technique-level
  // id when COV carries one that isn't already among the leaves.
  function leavesFor(techId) {
    let leaves = [];
    if (typeof findTechnique === "function") {
      const r = findTechnique(techId);
      const subs = r && r.technique.subtechniques;
      if (subs && Object.keys(subs).length) {
        leaves = Object.values(subs).map((s) => s.id);
      }
    }
    if (!leaves.length) leaves = [techId];
    if (COV[techId] && leaves.indexOf(techId) < 0) leaves.unshift(techId);
    return leaves;
  }

  // ── Technique-card badge: one count-pill per verdict, side by side ──────────
  function badge(card) {
    if (card.dataset.nos3Done) return;
    const id = card.dataset.id;
    if (!id) return;
    const cells = leavesFor(id).map((lid) => statusForId(lid).cls);
    card.dataset.nos3Done = "1";
    const cnt = {};
    cells.forEach((c) => { cnt[c] = (cnt[c] || 0) + 1; });
    // One original-style pill per verdict present; the number of sub-techniques
    // is inside the pill and the colour (matching the legend) carries the meaning
    // — no "NOS3" tag, no status words on the card.
    const el = document.createElement("div");
    el.className = "nos3-badge";
    el.innerHTML = ORDER.filter((k) => cnt[k]).map((k) =>
      "<span class='nos3-pill " + k + "' title='" + cnt[k] + " " + LABEL[k] + "'>" + cnt[k] + "</span>"
    ).join("");
    // Place the pills inline next to the technique ID (not on their own line):
    // wrap the id + pills together so the header's space-between keeps them left
    // and the base sub-technique-count indicator right.
    const header = card.querySelector(".technique-header");
    const idEl = header && header.querySelector(".technique-id");
    if (header && idEl) {
      let wrap = header.querySelector(".nos3-idwrap");
      if (!wrap) {
        wrap = document.createElement("span");
        wrap.className = "nos3-idwrap";
        header.insertBefore(wrap, idEl);
        wrap.appendChild(idEl);
      }
      wrap.appendChild(el);
    } else {
      card.appendChild(el);
    }
    card.classList.add("nos3-evaluated");
  }

  function badgeAll() {
    document.querySelectorAll(".technique-card[data-id]").forEach(badge);
  }

  // "Top fields / review" column. For detected techniques: the pipe-separated
  // "field:pct|…" SHAP explanation, rendered as a compact bar chart. For
  // out-of-scope / not-applicable techniques: a prose review (why it can't be seen
  // or why it can't run / what would be needed) so no such cell is ever blank.
  function whyCell(c) {
    if (c && c.review) {
      const t = String(c.review).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
      return "<td class='nos3-why nos3-review'>" + t + "</td>";
    }
    const expl = c ? c.explanation : "";
    if (!expl) return "<td class='nos3-why'>—</td>";
    const rows = expl.split("|").map(function (tok) {
      const i = tok.lastIndexOf(":");
      const name = i < 0 ? tok : tok.slice(0, i);
      const pct = i < 0 ? 0 : (parseInt(tok.slice(i + 1), 10) || 0);
      return (
        "<div class='nos3-why-row' title='" + name + " — " + pct + "%'>" +
        "<span class='nos3-why-fill' style='width:" + pct + "%'></span>" +
        "<span class='nos3-why-lab'>" + name + "</span>" +
        "<span class='nos3-why-pct'>" + pct + "%</span></div>"
      );
    }).join("");
    return "<td class='nos3-why'>" + rows + "</td>";
  }

  function statusPill(cls, gate) {
    const lab = cls === "det" && gate ? "detected (gate)" : LABEL[cls];
    return "<span class='nos3-pill " + cls + "'>" + lab + "</span>";
  }

  function injectModalPanel(techId) {
    const host = document.getElementById("techniqueDescription");
    if (!host) return;
    const old = document.getElementById("nos3-panel");
    if (old) old.remove();
    const leaves = leavesFor(techId);
    const resolved = leaves.map((lid) => ({ id: lid, s: statusForId(lid) }));
    if (!resolved.some((x) => x.s.cls !== "none")) return; // nothing to say
    const rows = resolved.map(({ id, s }) => {
      const c = s.c;
      const rec = c.incident_total ? c.incident_detected + "/" + c.incident_total : "—";
      const lab = (c.label_ok != null && c.incident_detected) ? " <span class='nos3-lab'>(" + c.label_ok + " labeled ✓)</span>" : "";
      const frame = (c.frame_rate != null) ? Math.round(c.frame_rate * 100) + "%" : "—";
      return (
        "<tr class='row-" + s.cls + "'><td class='nid'>" + id + "</td><td class='nos3-name'>" + (c.name || "") +
        "</td><td>" + statusPill(s.cls, c.gate) + "</td>" +
        "<td>" + (c.tier || "—") + "</td><td>" + (c.signal || "—") + "</td>" +
        "<td>" + frame + "</td><td class='nos3-inc'>" + rec + lab + "</td>" +
        whyCell(c) + "</tr>"
      );
    }).join("");
    const div = document.createElement("div");
    div.id = "nos3-panel";
    div.className = "nos3-panel";
    div.innerHTML =
      "<div class='nos3-panel-h'>NOS3/OnAIR Detection Coverage" +
      "<span class='nos3-sub'>" + (META.model || "") + "</span></div>" +
      "<div class='nos3-table-wrap'><table class='nos3-table'><thead><tr>" +
      "<th>Sub-technique</th><th>Name</th><th>Verdict</th><th>Classifier tier</th>" +
      "<th>Signal class</th><th title='frame-level SUNSAFE catch rate'>Frame catch</th>" +
      "<th title='incident-level recall across corpus instances'>Incident</th>" +
      "<th title='detected: top telemetry fields (SHAP, NOS3-311/312). out-of-scope / n/a: why it can%27t be seen or run.'>" +
      "Top fields / review</th>" +
      "</tr></thead><tbody>" + rows + "</tbody></table></div>" +
      "<div class='nos3-foot'>Each row is one sub-technique with its <b>own</b> verdict — a " +
      "technique is a mix, never one colour. <b>detected</b> = caught on the labeled corpus " +
      "(≥1 alert), or <b>detected (gate)</b> when the dynamics-IF misses it by design but a " +
      "complementary gate (rule-gate R1–R10, consistency-check, or staleness-check, named " +
      "under \"Top fields / review\") caught it live. <b>out of scope</b> = applies to NOS3 but emits no telemetry " +
      "signal (Section C). <b>not applicable</b> = the attack can't run against NOS3 at all " +
      "(off-board / not-modelled, Section D). <b>not evaluated</b> = a real sub-technique not " +
      "yet assessed. \"Frame catch\" is the per-frame SUNSAFE flag rate. Signal class: ON_BOARD " +
      "(visible) · OBFUSCATION (self-hidden) · UNSUBSCRIBED (not monitored) · CONCEPTUAL (no-op).</div>";
    host.parentNode.insertBefore(div, host.nextSibling);
  }

  // Embedded legend rendered into the #nos3-embed slot on the matrix toolbar.
  function addLegend() {
    if (document.getElementById("nos3-legend")) return;
    const rh = META.incident_recall_headline != null
      ? Math.round(META.incident_recall_headline * 100) + "%" : "";
    const L = document.createElement("div");
    L.id = "nos3-legend";
    L.className = "nos3-legend";
    L.innerHTML =
      "<strong title='corpus incident recall " + rh + "'>NOS3/OnAIR</strong>" +
      "<span class='nos3-pill det'>detected</span>" +
      "<span class='nos3-pill part'>partial</span>" +
      "<span class='nos3-pill miss'>not detected</span>" +
      "<span class='nos3-pill none'>not evaluated</span>" +
      "<span class='nos3-pill oos'>out of scope</span>" +
      "<span class='nos3-pill na'>not applicable</span>";
    const slot = document.getElementById("nos3-embed") || document.body;
    slot.appendChild(L);
  }

  // Per-status colours, shared by pills and segmented-bar blocks.
  const C = {
    det: ["rgba(34,197,94,.16)", "#16a34a", "rgba(34,197,94,.45)", "#22c55e"],
    part: ["rgba(245,158,11,.16)", "#d97706", "rgba(245,158,11,.45)", "#f59e0b"],
    miss: ["rgba(239,68,68,.15)", "#dc2626", "rgba(239,68,68,.45)", "#ef4444"],
    mon: ["rgba(59,130,246,.15)", "#2563eb", "rgba(59,130,246,.45)", "#3b82f6"],
    oos: ["rgba(148,163,184,.18)", "#64748b", "rgba(148,163,184,.45)", "#94a3b8"],
  };
  let pillCss = "";
  Object.keys(C).forEach((k) => {
    pillCss += ".nos3-pill." + k + "{background:" + C[k][0] + ";color:" + C[k][1] + ";border-color:" + C[k][2] + "}";
  });

  const CSS =
    // badge: count-pills inline next to the technique ID
    ".nos3-badge{display:inline-flex;flex-wrap:wrap;gap:.25rem;vertical-align:middle}" +
    ".nos3-idwrap{display:inline-flex;align-items:center;gap:.3rem;flex-wrap:wrap;min-width:0}" +
    ".technique-card.nos3-evaluated{position:relative}" +
    // pills (shared by card counts, legend, and modal). Card pills hold a count;
    // the colour (matching the legend) carries the meaning.
    ".nos3-pill{font-family:var(--font-mono,monospace);font-size:.64rem;font-weight:600;padding:.1rem .4rem;" +
    "border-radius:4px;border:1px solid transparent;white-space:nowrap;display:inline-block;" +
    "min-width:1.1em;text-align:center}" +
    ".nos3-pill.na{background:transparent;color:#64748b;border:1px dashed rgba(148,163,184,.6)}" +
    ".nos3-pill.none{background:rgba(59,130,246,.15);color:#2563eb;border-color:rgba(59,130,246,.45)}" +
    pillCss +
    // modal panel
    ".nos3-panel{margin:1rem 0;border:1px solid var(--border-color,#2a3344);border-radius:8px;" +
    "background:var(--bg-secondary,#11161f);overflow:hidden}" +
    ".nos3-panel-h{padding:.6rem .8rem;font-weight:700;background:rgba(59,130,246,.1);" +
    "border-bottom:1px solid var(--border-color,#2a3344);display:flex;justify-content:space-between;align-items:center}" +
    ".nos3-sub{font-family:var(--font-mono,monospace);font-size:.62rem;font-weight:500;opacity:.7}" +
    ".nos3-table{width:100%;border-collapse:collapse;font-size:.72rem}" +
    ".nos3-table th,.nos3-table td{padding:.35rem .55rem;text-align:left;border-bottom:1px solid var(--border-color,#222b38)}" +
    ".nos3-table th{font-size:.6rem;text-transform:uppercase;letter-spacing:.04em;opacity:.65}" +
    ".nos3-table td.nid,.nos3-table .nid{font-family:var(--font-mono,monospace);font-weight:600;white-space:nowrap}" +
    ".nos3-table td.nos3-name{white-space:nowrap}" +
    ".nos3-table td.nos3-inc{white-space:nowrap}" +
    ".nos3-table tr.row-none td,.nos3-table tr.row-na td{opacity:.72}" +
    ".nos3-lab{opacity:.6;font-size:.62rem}" +
    ".nos3-table-wrap{overflow-x:auto}" +
    ".nos3-table td.nos3-why{min-width:230px;vertical-align:middle}" +
    ".nos3-table td.nos3-review{font-size:.72rem;line-height:1.35;color:#64748b;" +
    "font-style:italic;white-space:normal;max-width:340px;vertical-align:middle}" +
    ".nos3-why-row{position:relative;display:flex;align-items:center;height:15px;margin:2px 0;" +
    "border-radius:3px;overflow:hidden;background:var(--bg-primary,#0f0f23);font-size:.62rem}" +
    ".nos3-why-fill{position:absolute;left:0;top:0;bottom:0;background:rgba(59,130,246,.30);z-index:0}" +
    ".nos3-why-lab{position:relative;z-index:1;padding-left:.35rem;white-space:nowrap;overflow:hidden;" +
    "text-overflow:ellipsis;max-width:155px;font-family:var(--font-mono,monospace)}" +
    ".nos3-why-pct{position:relative;z-index:1;margin-left:auto;padding:0 .35rem;" +
    "font-variant-numeric:tabular-nums;opacity:.9}" +
    ".nos3-foot{padding:.5rem .8rem;font-size:.64rem;opacity:.72;line-height:1.5}" +
    ".nos3-legend{display:flex;gap:.3rem;align-items:center;flex-wrap:wrap;font-size:.66rem}" +
    ".nos3-legend strong{font-size:.7rem;margin-right:.2rem;color:var(--text-secondary)}";

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
      console.log("[nos3] coverage overlay active:", Object.keys(COV).length, "evaluated techniques");
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
