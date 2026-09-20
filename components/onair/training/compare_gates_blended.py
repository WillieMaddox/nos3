#!/usr/bin/env python3
"""Replay the three rule gates over interleaved vs blended telemetry.

WHY THE GATES ARE THE INTERESTING TEST
--------------------------------------
Neither model gained much from de-interleaving: the classifier moved +0.034
macro-F1, and the IF's recall doubled off a base so low it does not matter. The
gates are different, because unlike the models they carry workarounds that exist
*only* because of the double buffer, and every one of them is a DESENSITISER:

  * consistency_check — rolling-window-min plus `Margin` (default 4) instead of
    the natural `new < prev`, because per-frame reads alternate. It cannot see a
    back-step smaller than the window minimum minus 4.
  * staleness_check  — tracks max-ADVANCEMENT rather than constancy, because a
    frozen counter oscillates between two buffer values instead of holding one.
  * rule_gate        — leaky-integrator flicker tolerance, a ClearLevel
    hysteresis sized for every-other-frame flicker, mode-switch oscillation
    tolerance, and a median-over-N filter on the time envelope because
    CFE_TIME.SecondsMET alternates between values ~4 s apart.

So the question is not "do the gates still work on blended data" — they must, the
artifact they compensate for is simply gone. It is whether the blended stream
changes what they FIRE on, which is what would justify relaxing the suppression.

⚠ This replays the REAL plugin classes, not a reimplementation, so the answer is
about deployed behaviour rather than about a model of it.

Usage:
    python3 components/onair/training/compare_gates_blended.py \\
        --corpus data/onair/corpus/rebuild_2026-09-10 --runs 12 \\
        --out data/onair/models/rebuild29/gates_blended_ab.json
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PLUGIN_ROOT = os.path.join(ROOT, "components/onair/fsw/plugins")
sys.path.insert(0, os.path.join(ROOT, "components/onair/fsw"))

GATES = {
    "rule_gate": ("rule_gate/rule_gate_plugin.py", "rule_gate_alert"),
    "consistency_check": ("consistency_check/consistency_check_plugin.py", "spoof_alert"),
    "staleness_check": ("staleness_check/staleness_check_plugin.py", "staleness_alert"),
}


REPLAY_INI = """[RULE_GATE]
WriteSideFile = false
WriteIncidentFile = false

[CONSISTENCY_CHECK]
WriteSideFile = false
WriteIncidentFile = false

[STALENESS_CHECK]
WriteSideFile = false
WriteIncidentFile = false
"""


def write_replay_ini(path: str) -> str:
    """Silence the gates' side-file and incident writers for an offline replay.

    Each gate defaults `SideFileOutputDir` to `../../../../data/onair/csv`, which
    is correct relative to the deployed `fsw/build/exe/cpu1/cf/onair/` and
    escapes the filesystem from anywhere else. A replay only needs the in-memory
    verdict from `render_reasoning()`, so turn the writers off rather than
    redirect them — that also keeps a replay from polluting the real csv dir with
    files indistinguishable from live ones.
    """
    with open(path, "w") as fh:
        fh.write(REPLAY_INI)
    os.environ["ONAIR_INI_FILE"] = path
    return path


def load_plugin(rel: str):
    path = os.path.join(PLUGIN_ROOT, rel)
    name = os.path.basename(path)[:-3]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod.Plugin


def replay(csv_path: str, attack_window, gate_key: str):
    """→ (nominal_frames, nominal_fires, attack_frames, attack_fires).

    `attack_window` is (start_row, end_row) in file row indices; everything
    before it is treated as the nominal baseline.
    """
    rel, alert_key = GATES[gate_key]
    Plugin = load_plugin(rel)
    with open(csv_path, newline="") as fh:
        rdr = csv.reader(fh)
        headers = next(rdr)
        plug = Plugin(gate_key, headers)
        a0, a1 = attack_window
        nom_n = nom_f = atk_n = atk_f = 0
        for i, row in enumerate(rdr):
            plug.update(low_level_data=row)
            fired = bool(plug.render_reasoning().get(alert_key))
            if a0 <= i <= a1:
                atk_n += 1
                atk_f += fired
            elif i < a0:
                nom_n += 1
                nom_f += fired
    return nom_n, nom_f, atk_n, atk_f


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--corpus", default="data/onair/corpus/rebuild_2026-09-10")
    p.add_argument("--interleaved-dir", default="data/onair/csv")
    p.add_argument("--blended-dir", default="data/onair/csv_blended")
    p.add_argument("--runs", type=int, default=12, help="how many corpus runs to replay")
    p.add_argument("--mode", default="SUNSAFE")
    p.add_argument("--out", required=True)
    args = p.parse_args()

    write_replay_ini(os.path.join(os.path.dirname(os.path.abspath(args.out)),
                                  "_gate_replay.ini"))

    man = json.load(open(os.path.join(args.corpus, "corpus_manifest.json")))
    runs = [r for r in man["runs"]
            if r["mode"] == args.mode and r.get("attack_windows")
            and r.get("sample_hz")][:args.runs]

    results = json.load(open(args.out)) if os.path.exists(args.out) else {}
    for r in runs:
        key = f"{r['technique']}_i{r['instance']}"
        if key in results:
            continue
        hz = r["sample_hz"]
        pre = r.get("pre_seconds") or 240
        a0 = int(pre * hz)
        a1 = min(int((pre + 300) * hz), r["frames"] - 1)
        entry = {"technique": r["technique"], "instance": r["instance"],
                 "csv": r["csv"], "gates": {}}
        for gate in GATES:
            entry["gates"][gate] = {}
            for variant, d in (("interleaved", args.interleaved_dir),
                               ("blended", args.blended_dir)):
                path = os.path.join(d, r["csv"])
                if not os.path.exists(path):
                    continue
                try:
                    nn, nf, an, af = replay(path, (a0, a1), gate)
                except Exception as e:                       # noqa: BLE001
                    entry["gates"][gate][variant] = {"error": str(e)[:120]}
                    continue
                entry["gates"][gate][variant] = {
                    "nominal_frames": nn, "nominal_fires": nf,
                    "attack_frames": an, "attack_fires": af,
                    "fp_rate": round(nf / nn, 5) if nn else None,
                    "detect_rate": round(af / an, 4) if an else None,
                }
        results[key] = entry
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        json.dump(results, open(args.out, "w"), indent=1)
        print(f"  {key}", flush=True)

    # ─── summary ───
    print(f"\n{'gate':<20}{'variant':<14}{'FP rate':>10}{'detect':>10}{'runs':>7}")
    print("-" * 61)
    for gate in GATES:
        for variant in ("interleaved", "blended"):
            nn = nf = an = af = k = 0
            for e in results.values():
                g = e["gates"].get(gate, {}).get(variant)
                if not g or "error" in g:
                    continue
                nn += g["nominal_frames"]; nf += g["nominal_fires"]
                an += g["attack_frames"];  af += g["attack_fires"]; k += 1
            if not k:
                continue
            print(f"{gate:<20}{variant:<14}{nf/nn if nn else 0:>10.5f}"
                  f"{af/an if an else 0:>10.4f}{k:>7}")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
