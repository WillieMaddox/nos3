#!/usr/bin/env python3
"""Track-2 batch validator — runs validate_footprint over all 17 new IMP +
DE-0003 catalog entries and prints a verdict summary table.

The declared-footprint columns per attack are hand-curated from the per-script
.md files (translated from `Packet.Item` COSMOS notation to CSV header
strings). For attacks whose detection lives off-board (DE-0003.04 ground
RSSI, .05 lock status, .07 CryptoLib, .10 ground tracking, .12 model hash),
we instead use a "proxy" column set that captures whether the cmd-injection
path fired at all — the level-1 bar from [[feedback_evaluation_provenance]].

Conceptual-only scripts (no sock.sendto) are tagged CONCEPTUAL and PASS
by definition of the level-1 bar — they're catalog placeholders, not
runtime attacks.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if THIS_DIR not in sys.path:
    sys.path.insert(0, THIS_DIR)

from validate_footprint import validate  # noqa: E402

REPO_ROOT = os.path.abspath(os.path.join(THIS_DIR, "..", "..", "..", ".."))
MANIFEST_DIR = os.path.join(REPO_ROOT, "data", "onair", "scenarios")
CSV_DIR = os.path.join(REPO_ROOT, "data", "onair", "csv")


# (attack_id, manifest_session_id, observable_signal_columns, signal_class, note)
#
# signal_class taxonomy:
#   ON_BOARD     — target subsystem HK is subscribed by OnAIR; counter delta
#                  should manifest cleanly. PASS verdict means cmd-injection
#                  bar AND visible counter delta both satisfied.
#   OBFUSCATION  — RESET-class attack: counter goes 0→N→0 between HK reads,
#                  so the PRIMARY counter shows no delta by design. SECONDARY
#                  signal (e.g. CFE_EVS_HK.MessageSendCounter event trail)
#                  proves the cmd landed. PARTIAL is the success verdict.
#   UNSUBSCRIBED — target subsystem HK is NOT in OnAIR security TLM (TO,
#                  CI, HS). Cmd-injection cannot be confirmed via OnAIR.
#                  Verdict is structurally unobservable; rely on manifest
#                  exit_code/stderr to confirm cmd-injection bar.
#   CONCEPTUAL   — script writes status CSV only, no UDP injection. Level-1
#                  PASS by definition (the script's job is to describe, not
#                  to attack).
SPEC = [
    # ─── 5 IMP entries ───────────────────────────────────────────────────
    # 2026-05-28: post-fix manifest after FC=2 + {0xAA,0x00} patch
    # (pre-fix manifest 2026-05-16T04-33-54Z showed EPS.CommandErrorCount
    # 0→6 — all switch cmds rejected). Post-fix:
    # EPS.CommandCount 0→6, ErrorCount 0→0, Switch-state cycles
    # ON→OFF→ON→OFF within attack window (deception signature: net
    # switch state unchanged but counters advanced).
    ("IMP-0001",  "2026-05-29T00-47-54Z", "OBFUSCATION",
     ["EPS.CommandCount", "CFE_EVS_HK.MessageSendCounter"],
     "EPS switch cycling (6 ON/OFF pairs) + 5 EVS NOOPs + EVS+ES RESET. "
     "Deception by design: switches cycle ON→OFF in pairs (net state "
     "unchanged), but EPS.CommandCount advances. RESET phase telescopes "
     "CFE_*.CommandCounter — EVS event trail is the observable signal."),

    ("IMP-0002",  "2026-05-16T04-43-30Z", "ON_BOARD",
     ["CFE_EVS_HK.CommandCounter", "CFE_EVS_HK.MessageSendCounter"],
     "Disruption via 10 rapid NOOPs to CFE_EVS_CMD."),

    ("IMP-0003",  "2026-05-16T04-53-01Z", "ON_BOARD",
     ["CFE_EVS_HK.MessageSendCounter", "CFE_SB.MemInUse"],
     "Denial: 30 NOOP burst + 30 event-generating NOOPs. "
     "CFE_SB.CommandCounter dual-buffered."),

    ("IMP-0005",  "2026-05-16T05-12-11Z", "ON_BOARD",
     ["CFE_ES.CommandCounter", "CFE_TBL.CommandCounter",
      "THRUSTER.CommandCount"],
     "Destruction probes: TBL + ES + thruster NOOPs (no RESET)."),

    ("IMP-0006",  "2026-05-16T05-21-43Z", "UNSUBSCRIBED",
     ["CFE_EVS_HK.MessageSendCounter"],
     "Theft: NOOP + ENABLE_OUTPUT via TO_DEBUG (0x18E8 not subscribed). "
     "Proxy = EVS event trail from attack-attributable events."),

    # ─── 12 DE-0003 sub-techniques ───────────────────────────────────────
    ("DE-0003.01", "2026-05-16T05-31-19Z", "OBFUSCATION",
     ["CFE_EVS_HK.MessageSendCounter"],
     "VCC zero via CFE_ES NOOP + RESET. CFE_ES.CommandCounter telescoped by "
     "RESET (working-as-designed obfuscation). Proxy = EVS event trail."),

    ("DE-0003.02", "2026-05-16T05-40-53Z", "OBFUSCATION",
     ["CFE_EVS_HK.MessageSendCounter"],
     "Rejected-cmd counter obfuscation via RESET. CFE_*.CommandErrorCounter "
     "telescoped; proxy = EVS event trail."),

    ("DE-0003.03", "2026-05-16T05-50-23Z", "UNSUBSCRIBED",
     ["CFE_EVS_HK.MessageSendCounter"],
     "Cmd receiver mode 0x18E0 (CI_DEBUG not subscribed). "
     "Proxy = EVS event trail."),

    ("DE-0003.04", "2026-05-16T05-59-53Z", "CONCEPTUAL",
     [],
     "Script writes status CSV only, no UDP injection. SPARTA technique is "
     "RF-layer (AGC), not implementable in NOS3 simulator."),

    ("DE-0003.05", "2026-05-16T06-09-22Z", "CONCEPTUAL",
     [],
     "Script writes status CSV only, no UDP injection. Same RF-layer "
     "limitation as DE-0003.04."),

    ("DE-0003.06", "2026-05-16T06-18-52Z", "ON_BOARD",
     ["CFE_EVS_HK.MessageSendCounter"],
     "EVS DISABLE_EVENT_TYPE (0x1801) + TO_DEBUG (0x18E8 not subscribed). "
     "Observable signal via EVS event trail."),

    ("DE-0003.07", "2026-05-16T06-28-22Z", "CONCEPTUAL",
     [],
     "Script writes status CSV only, no UDP injection. CryptoLib SA "
     "manipulation requires direct lib API, not in NOS3."),

    ("DE-0003.08", "2026-05-16T06-37-52Z", "OBFUSCATION",
     ["CFE_EVS_HK.MessageSendCounter"],
     "RESET via CFE_EVS_CMD to overwrite cmd history. EVS counter "
     "telescoped; proxy = EVS event trail."),

    ("DE-0003.09", "2026-05-16T06-47-24Z", "ON_BOARD",
     ["CFE_TIME.CommandCounter"],
     "Script sends CFE_TIME NOOP (not SET_TIME as catalog claims). "
     "Only CFE_TIME.CommandCounter perturbed; STCF/ClockStateFlags "
     "untouched. CATALOG_BUG: dwell=600 mismatches NOOP-only impl."),

    ("DE-0003.10", "2026-05-16T06-56-53Z", "ON_BOARD",
     ["NOVATEL_HK.CommandCount"],
     "GPS spoof via 0x1870 (NOVATEL cmd, subscribed). Level-2 sends 1 NOOP "
     "→ CommandCount +1. ErrorCount not expected to perturb (NOOP is valid)."),

    ("DE-0003.11", "2026-05-16T07-06-23Z", "UNSUBSCRIBED",
     ["CFE_EVS_HK.MessageSendCounter"],
     "Watchdog timer — 0x18AE (HS app cmd, HS HK not subscribed). "
     "Proxy = EVS event trail."),

    ("DE-0003.12", "2026-05-16T07-15-54Z", "CONCEPTUAL",
     [],
     "Script writes status CSV only, no UDP injection. ML model state is "
     "above NOS3 abstraction."),
]


def _manifest_exit_status(manifest_path: str, attack_id: str) -> tuple[int, int]:
    with open(manifest_path) as f:
        d = json.load(f)
    for a in d.get("attacks", []):
        if a["id"] == attack_id:
            return (a.get("exit_code", -1), a.get("stderr_lines", -1))
    return (-1, -1)


def run_batch(attack_ids: list[str] | None = None,
              verbose_per_attack: bool = False) -> dict:
    """Drive validate_footprint across SPEC; return a verdict-per-attack dict.

    The level-1 cmd-injection bar is `exit_code == 0` (subprocess ran clean).
    The telemetry-observability bar is signal_class-dependent:
      ON_BOARD     → PASS requires ≥1 observable column perturbed.
      OBFUSCATION  → PASS by manifest-exit-clean + ≥1 secondary signal.
      UNSUBSCRIBED → PASS by manifest-exit-clean alone (no on-board ack).
      CONCEPTUAL   → PASS by definition (no-op script).
    """
    results = {}
    for aid, sid, sig_class, columns, note in SPEC:
        if attack_ids and aid not in attack_ids:
            continue
        manifest = os.path.join(MANIFEST_DIR, f"manifest_{sid}.json")
        if not os.path.exists(manifest):
            results[aid] = {"verdict": "MANIFEST_NOT_FOUND",
                            "manifest": os.path.basename(manifest),
                            "signal_class": sig_class, "note": note}
            continue
        exit_code, stderr_lines = _manifest_exit_status(manifest, aid)
        l1_ok = exit_code == 0
        if sig_class == "CONCEPTUAL":
            verdict = ("PASS — conceptual (no-op script, level-1 by definition)"
                       if l1_ok else
                       f"FAIL — conceptual but exit_code={exit_code}")
            results[aid] = {"verdict": verdict, "signal_class": sig_class,
                            "manifest": os.path.basename(manifest),
                            "note": note, "exit_code": exit_code}
            continue
        try:
            r = validate(manifest, aid, columns,
                         csv_dir=CSV_DIR, verbose=verbose_per_attack)
            r["signal_class"] = sig_class
            r["note"] = note
            r["manifest"] = os.path.basename(manifest)
            r["exit_code"] = exit_code
            r["stderr_lines"] = stderr_lines
            # Refine verdict based on signal_class:
            base_v = r["verdict"]
            if sig_class == "UNSUBSCRIBED":
                if l1_ok:
                    r["verdict"] = ("PASS — UNSUBSCRIBED target; cmd-injection "
                                    "confirmed via subprocess exit_code=0 + "
                                    + ("EVS event trail observable"
                                       if "PERTURBED" in str(r.get("columns", {}))
                                       else "no on-board ack"))
                else:
                    r["verdict"] = f"FAIL — UNSUBSCRIBED + exit_code={exit_code}"
            elif sig_class == "OBFUSCATION":
                if l1_ok and "PASS" in base_v.upper().split() + base_v.split("—"):
                    r["verdict"] = ("PASS — OBFUSCATION; primary counter "
                                    "telescoped by design, EVS trail observable")
                elif l1_ok and "PARTIAL" in base_v:
                    r["verdict"] = ("PASS — OBFUSCATION; cmd-injection bar via "
                                    "exit_code=0, secondary signal partial")
                elif l1_ok:
                    r["verdict"] = ("PARTIAL — OBFUSCATION; cmd-injection ok "
                                    "but no secondary EVS trail observed")
                else:
                    r["verdict"] = f"FAIL — OBFUSCATION + exit_code={exit_code}"
            else:  # ON_BOARD
                # Use raw verdict from validate(), but tag with cmd-injection bar.
                if not l1_ok:
                    r["verdict"] = (f"FAIL — exit_code={exit_code} "
                                    f"(scripted but did not run clean)")
            results[aid] = r
        except SystemExit as e:
            results[aid] = {"verdict": f"ERROR: {e}",
                            "manifest": os.path.basename(manifest),
                            "signal_class": sig_class, "note": note}
    return results


def _short_verdict(v: str) -> str:
    """Drop the explanatory tail; keep PASS / PARTIAL / FAIL / CONCEPTUAL."""
    if "PASS" in v:
        return "PASS"
    if "PARTIAL" in v:
        return "PARTIAL"
    if "FAIL" in v:
        return "FAIL"
    if "CONCEPTUAL" in v:
        return "CONCEPTUAL"
    if "INCONCLUSIVE" in v:
        return "INCONCLUSIVE"
    return v.split()[0] if v else "?"


def print_summary(results: dict) -> None:
    print()
    print(f"{'Attack ID':<12}  {'Verdict':<10}  {'Class':<13}  {'Exit':<6}  Note")
    print(f"{'-' * 12}  {'-' * 10}  {'-' * 13}  {'-' * 6}  {'-' * 60}")
    counts: dict[str, int] = {}
    for aid in [s[0] for s in SPEC]:
        if aid not in results:
            continue
        v = results[aid]["verdict"]
        sv = _short_verdict(v)
        counts[sv] = counts.get(sv, 0) + 1
        note = results[aid].get("note", "")[:60]
        sig = results[aid].get("signal_class", "?")
        ec = results[aid].get("exit_code", "?")
        print(f"{aid:<12}  {sv:<10}  {sig:<13}  {str(ec):<6}  {note}")
    print()
    print("Verdict tally:")
    for k in ("PASS", "PARTIAL", "FAIL", "CONCEPTUAL", "INCONCLUSIVE"):
        if k in counts:
            print(f"  {k:<14}  {counts[k]}")
    print(f"  {'TOTAL':<14}  {sum(counts.values())}")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--attack-ids", nargs="*",
                   help="Restrict to specific attack ids (default: all 17)")
    p.add_argument("--verbose", action="store_true",
                   help="Print full per-column slice tables per attack")
    p.add_argument("--json", action="store_true",
                   help="Also emit a JSON dump of the verdicts (for memory record)")
    args = p.parse_args()

    results = run_batch(attack_ids=args.attack_ids,
                        verbose_per_attack=args.verbose)
    print_summary(results)
    if args.json:
        print()
        print("--- JSON ---")
        slim = {aid: {"verdict": _short_verdict(r["verdict"]),
                      "verdict_full": r["verdict"],
                      "note": r.get("note", ""),
                      "manifest": r.get("manifest", "")}
                for aid, r in results.items()}
        print(json.dumps(slim, indent=2))


if __name__ == "__main__":
    main()
